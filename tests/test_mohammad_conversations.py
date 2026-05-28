"""Unit tests for the conversation endpoints (Step 4E) and agent_service wiring (Step 4D).

Covers:
- agent_service.process_message() returns intent field (4D)
- POST /message: success, validation, history load/save, error propagation
- GET /{session_id}: history retrieval, strips system/tool messages
- _load_history / _save_history Redis helpers
- Schema validation (MessageRequest min_length, max_length)

FastAPI-dependent tests are skipped gracefully when the package is absent
(same pattern as test_mohammad_rag.py).
"""

import asyncio
import json
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ---------------------------------------------------------------------------
# Availability guards
# ---------------------------------------------------------------------------

try:
    import fastapi  # noqa: F401
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

try:
    import pydantic  # noqa: F401
    HAS_PYDANTIC = True
except ImportError:
    HAS_PYDANTIC = False


def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Redis history helpers — tested without importing FastAPI
# ---------------------------------------------------------------------------


class TestHistoryHelpers(unittest.TestCase):
    """_load_history and _save_history use only json/logging — no FastAPI needed."""

    def setUp(self):
        if not HAS_FASTAPI:
            self.skipTest("fastapi not installed")
        from apps.api.app.api.v1.conversations import _load_history, _save_history
        self._load = _load_history
        self._save = _save_history

    def test_load_no_redis_returns_empty(self):
        self.assertEqual(run(self._load(None, "t1", "s1")), [])

    def test_load_cache_miss_returns_empty(self):
        redis = MagicMock()
        redis.get = AsyncMock(return_value=None)
        self.assertEqual(run(self._load(redis, "t1", "s1")), [])

    def test_load_returns_stored_messages(self):
        stored = [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}]
        redis = MagicMock()
        redis.get = AsyncMock(return_value=json.dumps(stored))
        self.assertEqual(run(self._load(redis, "t1", "s1")), stored)

    def test_load_redis_error_returns_empty(self):
        redis = MagicMock()
        redis.get = AsyncMock(side_effect=ConnectionError("Redis down"))
        self.assertEqual(run(self._load(redis, "t1", "s1")), [])

    def test_save_no_redis_is_noop(self):
        run(self._save(None, "t1", "s1", [{"role": "user", "content": "hi"}]))

    def test_save_calls_redis_set_with_correct_key(self):
        redis = MagicMock()
        redis.set = AsyncMock()
        messages = [{"role": "user", "content": "hi"}]
        run(self._save(redis, "t1", "s1", messages))
        redis.set.assert_awaited_once()
        key, value = redis.set.call_args[0][:2]
        self.assertEqual(key, "conv:t1:s1")
        self.assertEqual(json.loads(value), messages)

    def test_save_sets_30min_ttl(self):
        redis = MagicMock()
        redis.set = AsyncMock()
        run(self._save(redis, "t1", "s1", []))
        self.assertEqual(redis.set.call_args[1]["ex"], 1800)

    def test_save_redis_error_does_not_raise(self):
        redis = MagicMock()
        redis.set = AsyncMock(side_effect=ConnectionError("Redis down"))
        run(self._save(redis, "t1", "s1", []))  # must not raise


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


@unittest.skipUnless(HAS_FASTAPI and HAS_PYDANTIC, "fastapi/pydantic not installed")
class TestSchemas(unittest.TestCase):

    def setUp(self):
        from apps.api.app.api.v1.conversations import (
            MessageRequest,
            MessageResponse,
            ConversationTurn,
            ConversationHistoryResponse,
        )
        self.MessageRequest = MessageRequest
        self.MessageResponse = MessageResponse
        self.ConversationTurn = ConversationTurn
        self.ConversationHistoryResponse = ConversationHistoryResponse

    def test_message_request_valid(self):
        req = self.MessageRequest(session_id="s1", message="Hello there")
        self.assertEqual(req.message, "Hello there")

    def test_message_request_empty_message_rejected(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            self.MessageRequest(session_id="s1", message="")

    def test_message_request_too_long_rejected(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            self.MessageRequest(session_id="s1", message="x" * 4097)

    def test_message_response_defaults(self):
        resp = self.MessageResponse(reply="hi", intent="greeting")
        self.assertIsNone(resp.action)
        self.assertEqual(resp.sources, [])
        self.assertEqual(resp.rag_confidence, 0.0)

    def test_conversation_history_response_shape(self):
        resp = self.ConversationHistoryResponse(
            session_id="s1",
            tenant_id="t1",
            messages=[self.ConversationTurn(role="user", content="hi")],
        )
        self.assertEqual(len(resp.messages), 1)


# ---------------------------------------------------------------------------
# send_message endpoint (called directly, no HTTP server needed)
# ---------------------------------------------------------------------------


@unittest.skipUnless(HAS_FASTAPI, "fastapi not installed")
class TestSendMessage(unittest.TestCase):

    def _pm_mock(self, intent="greeting", reply="Hello!", action=None):
        return AsyncMock(return_value={
            "reply": reply, "intent": intent,
            "action": action, "sources": [], "rag_confidence": 0.0,
        })

    def test_returns_reply_and_intent(self):
        import apps.api.app.api.v1.conversations as conv_mod
        from apps.api.app.api.v1.conversations import MessageRequest

        redis = MagicMock()
        redis.get = AsyncMock(return_value=None)
        redis.set = AsyncMock()

        with patch.object(conv_mod, "process_message", self._pm_mock("greeting", "Hi there!")), \
             patch.object(conv_mod, "_get_redis", return_value=redis), \
             patch.object(conv_mod, "_get_llm", return_value=None), \
             patch.object(conv_mod, "_get_classifier_url", return_value=None):
            result = run(conv_mod.send_message(
                payload=MessageRequest(session_id="s1", message="Hello"),
                tenant_id="t1", db=None,
            ))

        self.assertEqual(result.reply, "Hi there!")
        self.assertEqual(result.intent, "greeting")
        self.assertIsNone(result.action)

    def test_history_loaded_and_passed_to_process_message(self):
        import apps.api.app.api.v1.conversations as conv_mod
        from apps.api.app.api.v1.conversations import MessageRequest

        stored = [{"role": "user", "content": "prior msg"}]
        mock_pm = self._pm_mock()
        redis = MagicMock()
        redis.get = AsyncMock(return_value=json.dumps(stored))
        redis.set = AsyncMock()

        with patch.object(conv_mod, "process_message", mock_pm), \
             patch.object(conv_mod, "_get_redis", return_value=redis), \
             patch.object(conv_mod, "_get_llm", return_value=None), \
             patch.object(conv_mod, "_get_classifier_url", return_value=None):
            run(conv_mod.send_message(
                payload=MessageRequest(session_id="s1", message="Hi"),
                tenant_id="t1", db=None,
            ))

        kw = mock_pm.call_args[1]
        self.assertEqual(kw["conversation_history"], stored)
        self.assertEqual(kw["tenant_id"], "t1")
        self.assertEqual(kw["session_id"], "s1")

    def test_history_saved_after_response(self):
        import apps.api.app.api.v1.conversations as conv_mod
        from apps.api.app.api.v1.conversations import MessageRequest

        redis = MagicMock()
        redis.get = AsyncMock(return_value=None)
        redis.set = AsyncMock()

        with patch.object(conv_mod, "process_message", self._pm_mock(reply="Hi!")), \
             patch.object(conv_mod, "_get_redis", return_value=redis), \
             patch.object(conv_mod, "_get_llm", return_value=None), \
             patch.object(conv_mod, "_get_classifier_url", return_value=None):
            run(conv_mod.send_message(
                payload=MessageRequest(session_id="s1", message="Hello"),
                tenant_id="t1", db=None,
            ))

        redis.set.assert_awaited_once()
        saved = json.loads(redis.set.call_args[0][1])
        self.assertIn("user", [m["role"] for m in saved])
        self.assertIn("assistant", [m["role"] for m in saved])

    def test_action_propagated(self):
        import apps.api.app.api.v1.conversations as conv_mod
        from apps.api.app.api.v1.conversations import MessageRequest

        redis = MagicMock()
        redis.get = AsyncMock(return_value=None)
        redis.set = AsyncMock()

        with patch.object(conv_mod, "process_message", self._pm_mock("lead_capture", action="lead_captured")), \
             patch.object(conv_mod, "_get_redis", return_value=redis), \
             patch.object(conv_mod, "_get_llm", return_value=None), \
             patch.object(conv_mod, "_get_classifier_url", return_value=None):
            result = run(conv_mod.send_message(
                payload=MessageRequest(session_id="s1", message="Call me"),
                tenant_id="t1", db=None,
            ))

        self.assertEqual(result.action, "lead_captured")

    def test_process_message_exception_raises_http_500(self):
        import apps.api.app.api.v1.conversations as conv_mod
        from apps.api.app.api.v1.conversations import MessageRequest
        from fastapi import HTTPException

        redis = MagicMock()
        redis.get = AsyncMock(return_value=None)
        redis.set = AsyncMock()

        with patch.object(conv_mod, "process_message", AsyncMock(side_effect=RuntimeError("boom"))), \
             patch.object(conv_mod, "_get_redis", return_value=redis), \
             patch.object(conv_mod, "_get_llm", return_value=None), \
             patch.object(conv_mod, "_get_classifier_url", return_value=None):
            with self.assertRaises(HTTPException) as ctx:
                run(conv_mod.send_message(
                    payload=MessageRequest(session_id="s1", message="Hello"),
                    tenant_id="t1", db=None,
                ))

        self.assertEqual(ctx.exception.status_code, 500)


# ---------------------------------------------------------------------------
# get_conversation endpoint
# ---------------------------------------------------------------------------


@unittest.skipUnless(HAS_FASTAPI, "fastapi not installed")
class TestGetConversation(unittest.TestCase):

    def test_strips_system_and_tool_messages(self):
        import apps.api.app.api.v1.conversations as conv_mod

        stored = [
            {"role": "system", "content": "You are a bot."},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
            {"role": "tool", "content": '{"results": []}'},
        ]
        redis = MagicMock()
        redis.get = AsyncMock(return_value=json.dumps(stored))

        with patch.object(conv_mod, "_get_redis", return_value=redis):
            result = run(conv_mod.get_conversation(session_id="s1", tenant_id="t1"))

        roles = [m.role for m in result.messages]
        self.assertNotIn("system", roles)
        self.assertNotIn("tool", roles)
        self.assertIn("user", roles)
        self.assertIn("assistant", roles)

    def test_empty_session_returns_empty_messages(self):
        import apps.api.app.api.v1.conversations as conv_mod

        redis = MagicMock()
        redis.get = AsyncMock(return_value=None)

        with patch.object(conv_mod, "_get_redis", return_value=redis):
            result = run(conv_mod.get_conversation(session_id="new-session", tenant_id="t1"))

        self.assertEqual(result.messages, [])

    def test_tenant_id_in_response(self):
        import apps.api.app.api.v1.conversations as conv_mod

        redis = MagicMock()
        redis.get = AsyncMock(return_value=None)

        with patch.object(conv_mod, "_get_redis", return_value=redis):
            result = run(conv_mod.get_conversation(session_id="s1", tenant_id="tenant-xyz"))

        self.assertEqual(result.tenant_id, "tenant-xyz")


# ---------------------------------------------------------------------------
# 4D: agent_service.process_message returns intent
# ---------------------------------------------------------------------------


class TestAgentServiceIntent(unittest.TestCase):

    def test_process_message_includes_intent(self):
        from apps.api.app.services import agent_service as svc

        mock_result = MagicMock()
        mock_result.reply = "Hello!"
        mock_result.intent = "greeting"
        mock_result.action = None
        mock_result.sources = []
        mock_result.rag_confidence = 0.0

        with patch.object(svc, "route", AsyncMock(return_value=mock_result)):
            result = run(svc.process_message(
                tenant_id="t1", session_id="s1", message="Hi",
                conversation_history=[], db_session=None,
            ))

        self.assertIn("intent", result)
        self.assertEqual(result["intent"], "greeting")

    def test_process_message_all_required_keys_present(self):
        from apps.api.app.services import agent_service as svc

        mock_result = MagicMock()
        mock_result.reply = "Here you go."
        mock_result.intent = "knowledge_search"
        mock_result.action = None
        mock_result.sources = [{"content_id": "c1"}]
        mock_result.rag_confidence = 0.75

        with patch.object(svc, "route", AsyncMock(return_value=mock_result)):
            result = run(svc.process_message(
                tenant_id="t1", session_id="s1",
                message="What is your policy?",
                conversation_history=[], db_session=None,
            ))

        for key in ("reply", "intent", "action", "sources", "rag_confidence"):
            self.assertIn(key, result)


if __name__ == "__main__":
    unittest.main()
