"""Unit tests for the bounded agent (Step 4B) and tools (Step 4C).

Covers:
- Tool definitions (schema completeness, only 3 tools)
- execute_tool dispatcher
- _trim_history
- _load_memory / _save_memory
- run_agent: direct answer, tool call, multi-turn, max-iterations cap,
  unapproved-tool block, no-llm fallback, action/sources propagation
"""

import asyncio
import json
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.agent.tools import (
    ALLOWED_TOOLS,
    TOOL_DEFINITIONS,
    execute_tool,
)
from services.agent.agent import (
    MAX_ITERATIONS,
    _trim_history,
    _load_memory,
    _save_memory,
    run_agent,
)


def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Helpers: mock LLM responses
# ---------------------------------------------------------------------------


def _make_tool_call(id_, name, arguments: dict):
    tc = MagicMock()
    tc.id = id_
    tc.function.name = name
    tc.function.arguments = json.dumps(arguments)
    return tc


def _text_response(text: str):
    msg = MagicMock()
    msg.content = text
    msg.tool_calls = None
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _tool_call_response(tool_calls: list):
    msg = MagicMock()
    msg.content = None
    msg.tool_calls = tool_calls
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------


class TestToolDefinitions(unittest.TestCase):

    def test_exactly_three_tools_defined(self):
        self.assertEqual(len(TOOL_DEFINITIONS), 3)

    def test_allowed_tools_matches_definitions(self):
        defined_names = {t["function"]["name"] for t in TOOL_DEFINITIONS}
        self.assertEqual(defined_names, ALLOWED_TOOLS)

    def test_rag_search_has_required_query_param(self):
        schema = next(t for t in TOOL_DEFINITIONS if t["function"]["name"] == "rag_search")
        self.assertIn("query", schema["function"]["parameters"]["required"])

    def test_capture_lead_requires_name_and_email(self):
        schema = next(t for t in TOOL_DEFINITIONS if t["function"]["name"] == "capture_lead")
        required = schema["function"]["parameters"]["required"]
        self.assertIn("name", required)
        self.assertIn("email", required)

    def test_escalate_requires_reason(self):
        schema = next(t for t in TOOL_DEFINITIONS if t["function"]["name"] == "escalate")
        self.assertIn("reason", schema["function"]["parameters"]["required"])


# ---------------------------------------------------------------------------
# execute_tool dispatcher
# ---------------------------------------------------------------------------


class TestExecuteTool(unittest.TestCase):

    def test_rag_search_calls_retrieval_fn(self):
        mock_result = MagicMock()
        mock_result.content_id = "c1"
        mock_result.chunk_index = 0
        mock_result.score = 0.85
        mock_result.chunk_text = "We are open 9-5."

        async def fake_retrieval(tenant_id, query, db, **kw):
            return [mock_result]

        result = run(execute_tool(
            "rag_search", {"query": "business hours"},
            tenant_id="t1", session_id="s1",
            retrieval_fn=fake_retrieval,
        ))
        self.assertEqual(len(result["results"]), 1)
        self.assertIn("We are open 9-5.", result["results"][0]["text"])

    def test_rag_search_empty_query_returns_error(self):
        result = run(execute_tool(
            "rag_search", {"query": "   "},
            tenant_id="t1", session_id="s1",
        ))
        self.assertEqual(result["results"], [])

    def test_capture_lead_missing_email_returns_error(self):
        result = run(execute_tool(
            "capture_lead", {"name": "Alice"},
            tenant_id="t1", session_id="s1",
        ))
        self.assertFalse(result["success"])
        self.assertIn("email", result["error"].lower())

    def test_capture_lead_no_db_returns_success(self):
        result = run(execute_tool(
            "capture_lead", {"name": "Alice", "email": "alice@example.com"},
            tenant_id="t1", session_id="s1",
            db_session=None,
        ))
        self.assertTrue(result["success"])
        self.assertEqual(result["action"], "lead_captured")

    def test_escalate_no_db_returns_success(self):
        result = run(execute_tool(
            "escalate", {"reason": "User wants human"},
            tenant_id="t1", session_id="s1",
            db_session=None,
        ))
        self.assertTrue(result["success"])
        self.assertEqual(result["action"], "escalated")

    def test_unknown_tool_returns_error(self):
        result = run(execute_tool(
            "delete_database", {},
            tenant_id="t1", session_id="s1",
        ))
        self.assertIn("error", result)


# ---------------------------------------------------------------------------
# _trim_history
# ---------------------------------------------------------------------------


class TestTrimHistory(unittest.TestCase):

    def _msg(self, content):
        return {"role": "user", "content": content}

    def test_trims_to_max_messages(self):
        msgs = [self._msg(f"msg {i}") for i in range(20)]
        trimmed = _trim_history(msgs, max_messages=10)
        self.assertLessEqual(len(trimmed), 10)
        # Most recent messages must be kept
        self.assertEqual(trimmed[-1]["content"], "msg 19")

    def test_trims_by_char_count(self):
        long_msg = self._msg("x" * 5000)
        msgs = [long_msg, long_msg, long_msg]
        trimmed = _trim_history(msgs, max_chars=6000)
        total = sum(len(m["content"]) for m in trimmed)
        self.assertLessEqual(total, 6000)

    def test_empty_history_returns_empty(self):
        self.assertEqual(_trim_history([]), [])

    def test_single_message_never_trimmed(self):
        msg = self._msg("x" * 20_000)
        trimmed = _trim_history([msg], max_chars=100)
        self.assertEqual(len(trimmed), 1)


# ---------------------------------------------------------------------------
# _load_memory / _save_memory
# ---------------------------------------------------------------------------


class TestMemory(unittest.TestCase):

    def test_load_memory_no_redis_returns_provided(self):
        history = [{"role": "user", "content": "hi"}]
        result = run(_load_memory("t", "s", None, history))
        self.assertEqual(result, history)

    def test_load_memory_redis_unavailable_returns_provided(self):
        redis = MagicMock()
        redis.get = AsyncMock(side_effect=ConnectionError("Redis down"))
        history = [{"role": "user", "content": "hi"}]
        result = run(_load_memory("t", "s", redis, history))
        self.assertEqual(result, history)

    def test_load_memory_uses_redis_when_available(self):
        stored = [{"role": "user", "content": "stored msg"}]
        redis = MagicMock()
        redis.get = AsyncMock(return_value=json.dumps(stored))
        result = run(_load_memory("t", "s", redis, []))
        self.assertEqual(result, stored)

    def test_save_memory_calls_redis_set(self):
        redis = MagicMock()
        redis.set = AsyncMock()
        run(_save_memory("t", "s", redis, [], [{"role": "user", "content": "hi"}]))
        redis.set.assert_awaited_once()
        key, value = redis.set.call_args[0][:2]
        self.assertEqual(key, "conv:t:s")
        saved = json.loads(value)
        self.assertEqual(saved[0]["content"], "hi")

    def test_save_memory_no_redis_is_noop(self):
        # Should not raise
        run(_save_memory("t", "s", None, [], [{"role": "user", "content": "hi"}]))


# ---------------------------------------------------------------------------
# run_agent
# ---------------------------------------------------------------------------


class TestRunAgent(unittest.TestCase):

    def _llm(self, side_effects):
        """Build a mock LLM client with a sequence of responses."""
        client = MagicMock()
        client.chat.completions.create = AsyncMock(side_effect=side_effects)
        return client

    def test_direct_text_answer(self):
        client = self._llm([_text_response("We open at 9am.")])
        result = run(run_agent("t1", "s1", "What time do you open?", [], llm_client=client))
        self.assertEqual(result["reply"], "We open at 9am.")
        self.assertIsNone(result["action"])
        self.assertEqual(result["sources"], [])

    def test_single_rag_search_then_answer(self):
        rag_tc = _make_tool_call("tc1", "rag_search", {"query": "opening hours"})
        rag_result = {
            "results": [{"source": 1, "content_id": "c1", "chunk_index": 0, "score": 0.9, "text": "9-5"}]
        }

        async def fake_retrieval(tenant_id, query, db, **kw):
            mock = MagicMock()
            mock.content_id = "c1"
            mock.chunk_index = 0
            mock.score = 0.9
            mock.chunk_text = "9-5"
            return [mock]

        client = self._llm([
            _tool_call_response([rag_tc]),
            _text_response("Our hours are 9-5."),
        ])

        result = run(run_agent(
            "t1", "s1", "When are you open?", [],
            llm_client=client,
            retrieval_fn=fake_retrieval,
        ))
        self.assertEqual(result["reply"], "Our hours are 9-5.")
        self.assertEqual(len(result["sources"]), 1)

    def test_lead_capture_action_propagated(self):
        capture_tc = _make_tool_call("tc1", "capture_lead", {"name": "Bob", "email": "bob@x.com"})
        client = self._llm([
            _tool_call_response([capture_tc]),
            _text_response("Thanks Bob, we'll be in touch!"),
        ])

        result = run(run_agent("t1", "s1", "I'd like a callback", [], llm_client=client))
        self.assertEqual(result["action"], "lead_captured")
        self.assertEqual(result["reply"], "Thanks Bob, we'll be in touch!")

    def test_escalate_action_propagated(self):
        esc_tc = _make_tool_call("tc1", "escalate", {"reason": "User angry"})
        client = self._llm([
            _tool_call_response([esc_tc]),
            _text_response("Connecting you to a human now."),
        ])

        result = run(run_agent("t1", "s1", "Get me a human!", [], llm_client=client))
        self.assertEqual(result["action"], "escalated")

    def test_unapproved_tool_is_blocked(self):
        bad_tc = _make_tool_call("tc1", "delete_all_data", {})
        client = self._llm([
            _tool_call_response([bad_tc]),
            _text_response("I couldn't do that."),
        ])

        result = run(run_agent("t1", "s1", "Delete everything", [], llm_client=client))
        # Agent must NOT crash and must return a reply
        self.assertIsInstance(result["reply"], str)

    def test_max_iterations_cap(self):
        """Agent must stop after max_iterations and return a graceful fallback (ROUT-07)."""
        bad_tc = _make_tool_call("tc1", "rag_search", {"query": "anything"})

        async def fake_retrieval(tenant_id, query, db, **kw):
            return []

        # Keep returning tool calls; the loop should break after max_iterations
        client = self._llm([_tool_call_response([bad_tc])] * 10)

        result = run(run_agent(
            "t1", "s1", "Tell me about X", [],
            llm_client=client,
            max_iterations=3,
            retrieval_fn=fake_retrieval,
        ))
        # Must have hit the limit and returned the fallback
        self.assertEqual(client.chat.completions.create.await_count, 3)
        self.assertIn("connect", result["reply"].lower())
        self.assertEqual(result["action"], "escalated")

    def test_no_llm_client_returns_fallback(self):
        result = run(run_agent("t1", "s1", "Hello", [], llm_client=None))
        self.assertIsInstance(result["reply"], str)
        self.assertNotEqual(result["reply"], "")

    def test_llm_exception_returns_fallback(self):
        client = MagicMock()
        client.chat.completions.create = AsyncMock(side_effect=RuntimeError("API error"))
        result = run(run_agent("t1", "s1", "Hello", [], llm_client=client))
        self.assertIsInstance(result["reply"], str)

    def test_result_keys_always_present(self):
        client = self._llm([_text_response("Hi there!")])
        result = run(run_agent("t1", "s1", "Hi", [], llm_client=client))
        for key in ("reply", "action", "sources", "rag_confidence"):
            self.assertIn(key, result)

    def test_memory_saved_after_direct_answer(self):
        redis = MagicMock()
        redis.get = AsyncMock(return_value=None)
        redis.set = AsyncMock()

        client = self._llm([_text_response("Sure!")])
        run(run_agent("t1", "s1", "Can you help?", [], llm_client=client, redis_client=redis))

        redis.set.assert_awaited_once()
        saved = json.loads(redis.set.call_args[0][1])
        roles = [m["role"] for m in saved]
        self.assertIn("user", roles)
        self.assertIn("assistant", roles)


if __name__ == "__main__":
    unittest.main()
