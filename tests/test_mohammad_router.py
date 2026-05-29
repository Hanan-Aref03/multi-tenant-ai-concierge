"""Unit tests for services/router/router.py (Step 4A).

Tests cover:
- _decide_route() routing logic
- classify_intent() fallback chain
- route() end-to-end paths: direct / rag / agent / graceful fallback
- logging fields (message hash format)
"""

import asyncio
import hashlib
import json
import sys
import types
import unittest
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Path bootstrap: make sure project root is on sys.path
# ---------------------------------------------------------------------------

import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


from services.router.classifier_client import normalize_classifier_intent
from services.router.classifier_service import classify_intent
from services.router.constants import CLASSIFIER_CONFIDENCE_THRESHOLD
from services.router.contracts import ClassifyResult, RouteResult
from services.router.routing_logging import _log_routing
from services.router.routing_policy import _decide_route
from services.router.router import route


def run(coro):
    """Run a coroutine in a fresh event loop."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# _decide_route tests
# ---------------------------------------------------------------------------


class TestDecideRoute(unittest.TestCase):
    def _cr(self, intent, confidence=0.95):
        return ClassifyResult(intent=intent, confidence=confidence, source="llm")

    def test_greeting_routes_direct(self):
        self.assertEqual(_decide_route(self._cr("greeting")), "direct")

    def test_off_topic_routes_direct(self):
        self.assertEqual(_decide_route(self._cr("off_topic")), "direct")

    def test_spam_routes_direct(self):
        self.assertEqual(_decide_route(self._cr("spam")), "direct")

    def test_faq_routes_rag(self):
        self.assertEqual(_decide_route(self._cr("faq")), "rag")

    def test_knowledge_search_routes_rag(self):
        self.assertEqual(_decide_route(self._cr("knowledge_search")), "rag")

    def test_lead_capture_routes_agent(self):
        self.assertEqual(_decide_route(self._cr("lead_capture")), "agent")

    def test_escalation_routes_agent(self):
        self.assertEqual(_decide_route(self._cr("escalation")), "agent")

    def test_low_confidence_always_routes_agent(self):
        threshold = CLASSIFIER_CONFIDENCE_THRESHOLD - 0.01
        for intent in ("greeting", "faq", "knowledge_search", "lead_capture", "escalation", "off_topic"):
            with self.subTest(intent=intent):
                cr = ClassifyResult(intent=intent, confidence=threshold, source="llm")
                self.assertEqual(_decide_route(cr), "agent")

    def test_exactly_at_threshold_routes_by_intent(self):
        cr = ClassifyResult(intent="faq", confidence=CLASSIFIER_CONFIDENCE_THRESHOLD, source="llm")
        self.assertEqual(_decide_route(cr), "rag")


class TestModelserverLabelNormalization(unittest.TestCase):
    def test_modelserver_labels_map_to_router_intents(self):
        self.assertEqual(normalize_classifier_intent("faq"), "faq")
        self.assertEqual(normalize_classifier_intent("support"), "knowledge_search")
        self.assertEqual(normalize_classifier_intent("sales_or_leads"), "lead_capture")
        self.assertEqual(normalize_classifier_intent("human_request"), "escalation")
        self.assertEqual(normalize_classifier_intent("spam"), "spam")
        self.assertEqual(normalize_classifier_intent("other"), "knowledge_search")


# ---------------------------------------------------------------------------
# classify_intent tests
# ---------------------------------------------------------------------------


class TestClassifyIntent(unittest.TestCase):

    def _make_llm_client(self, intent="faq", confidence=0.9):
        """Build a mock LLM client that returns a valid classification JSON."""
        client = MagicMock()
        completion = MagicMock()
        completion.choices[0].message.content = json.dumps(
            {"intent": intent, "confidence": confidence}
        )
        client.chat.completions.create = AsyncMock(return_value=completion)
        return client

    def test_llm_fallback_returns_correct_intent(self):
        client = self._make_llm_client(intent="escalation", confidence=0.88)
        result = run(classify_intent("tenant-1", "I want a human", [], None, client))
        self.assertEqual(result.intent, "escalation")
        self.assertAlmostEqual(result.confidence, 0.88)
        self.assertEqual(result.source, "llm")

    def test_no_classifier_no_llm_returns_fallback(self):
        result = run(classify_intent("tenant-1", "hello", [], None, None))
        self.assertEqual(result.intent, "knowledge_search")
        self.assertEqual(result.confidence, 0.0)
        self.assertEqual(result.source, "fallback")

    def test_llm_unknown_intent_falls_to_fallback(self):
        client = MagicMock()
        completion = MagicMock()
        completion.choices[0].message.content = json.dumps(
            {"intent": "unknown_intent", "confidence": 0.9}
        )
        client.chat.completions.create = AsyncMock(return_value=completion)
        result = run(classify_intent("tenant-1", "test", [], None, client))
        self.assertEqual(result.source, "fallback")

    def test_llm_invalid_json_falls_to_fallback(self):
        client = MagicMock()
        completion = MagicMock()
        completion.choices[0].message.content = "not valid json"
        client.chat.completions.create = AsyncMock(return_value=completion)
        result = run(classify_intent("tenant-1", "test", [], None, client))
        self.assertEqual(result.source, "fallback")

    def test_classifier_server_error_falls_to_llm(self):
        """If model server raises, the LLM fallback should be used."""
        client = self._make_llm_client(intent="greeting", confidence=0.97)
        # classifier_url is set but httpx will fail (no server running)
        result = run(classify_intent("tenant-1", "hi", [], "http://localhost:9999", client))
        # Should succeed via LLM fallback
        self.assertEqual(result.intent, "greeting")
        self.assertEqual(result.source, "llm")


# ---------------------------------------------------------------------------
# route() tests
# ---------------------------------------------------------------------------


class TestRoute(unittest.TestCase):

    def _make_llm_client(self, intent="greeting", confidence=0.98):
        client = MagicMock()
        completion = MagicMock()
        completion.choices[0].message.content = json.dumps(
            {"intent": intent, "confidence": confidence}
        )
        client.chat.completions.create = AsyncMock(return_value=completion)
        return client

    def test_greeting_returns_direct(self):
        client = self._make_llm_client("greeting", 0.98)
        result = run(route("t1", "s1", "Hello!", [], llm_client=client))
        self.assertEqual(result.routed_to, "direct")
        self.assertEqual(result.intent, "greeting")
        self.assertIsNone(result.action)

    def test_off_topic_returns_direct_refusal(self):
        client = self._make_llm_client("off_topic", 0.99)
        result = run(route("t1", "s1", "How do I bake bread?", [], llm_client=client))
        self.assertEqual(result.routed_to, "direct")
        self.assertIn("services", result.reply.lower())

    def test_faq_routes_to_rag(self):
        client = self._make_llm_client("faq", 0.95)

        mock_rag = MagicMock()
        mock_rag.answer_from_knowledge = AsyncMock(return_value={
            "answer": "Our hours are 9-5.",
            "sources": [{"content_id": "c1", "chunk_index": 0, "score": 0.8}],
            "confidence": 0.8,
        })

        result = run(route("t1", "s1", "What are your hours?", [], llm_client=client, rag_service=mock_rag))
        self.assertEqual(result.routed_to, "rag")
        self.assertEqual(result.reply, "Our hours are 9-5.")
        self.assertEqual(len(result.sources), 1)

    def test_lead_capture_routes_to_agent(self):
        client = self._make_llm_client("lead_capture", 0.97)
        db = MagicMock()
        db.execute = AsyncMock()
        db.commit = AsyncMock()

        async def fake_agent(**kwargs):
            return {"reply": "Great, I've saved your contact info.", "action": "lead_captured", "sources": []}

        result = run(route(
            "t1",
            "s1",
            "I want to buy. My name is Rayan and my email is rayan@example.com",
            [],
            db_session=db,
            llm_client=client,
            agent_fn=fake_agent,
        ))
        self.assertEqual(result.routed_to, "direct")
        self.assertEqual(result.action, "lead_captured")
        db.execute.assert_awaited_once()
        self.assertEqual(db.execute.call_args[0][1]["tenant_id"], "t1")
        self.assertEqual(json.loads(db.execute.call_args[0][1]["metadata"])["conversation_id"], "s1")

    def test_escalation_routes_to_agent(self):
        client = self._make_llm_client("escalation", 0.99)

        async def fake_agent(**kwargs):
            return {"reply": "Connecting you to a human.", "action": "escalated", "sources": []}

        result = run(route("t1", "s1", "I need a real person", [], llm_client=client, agent_fn=fake_agent))
        self.assertEqual(result.routed_to, "agent")
        self.assertEqual(result.action, "escalated")

    def test_pricing_contact_email_routes_to_lead_capture(self):
        client = self._make_llm_client("faq", 0.95)
        db = MagicMock()
        db.execute = AsyncMock()
        db.commit = AsyncMock()

        result = run(route(
            "tenant-real",
            "conv-1",
            "Can I get pricing? I want a sales representative to contact me at rayan@example.com",
            [],
            db_session=db,
            llm_client=client,
        ))

        self.assertEqual(result.intent, "lead_capture")
        self.assertEqual(result.action, "lead_captured")
        self.assertIn("captured your request", result.reply)
        params = db.execute.call_args[0][1]
        self.assertEqual(params["tenant_id"], "tenant-real")
        self.assertEqual(params["email"], "rayan@example.com")
        metadata = json.loads(params["metadata"])
        self.assertEqual(metadata["conversation_id"], "conv-1")
        self.assertIn("pricing", metadata["message"].lower())

    def test_buy_contact_me_message_routes_to_lead_capture(self):
        client = self._make_llm_client("escalation", 0.4)
        db = MagicMock()
        db.execute = AsyncMock()
        db.commit = AsyncMock()

        result = run(route(
            "tenant-real",
            "conv-2",
            "I want to buy your service. Please contact me. My name is Rayan Halabi and my email is rayan@example.com",
            [],
            db_session=db,
            llm_client=client,
        ))

        self.assertEqual(result.intent, "lead_capture")
        self.assertEqual(result.action, "lead_captured")
        params = db.execute.call_args[0][1]
        self.assertEqual(params["tenant_id"], "tenant-real")
        self.assertEqual(params["full_name"], "Rayan Halabi")

    def test_sales_tenant_scope_uses_route_tenant(self):
        client = self._make_llm_client("knowledge_search", 0.2)
        db = MagicMock()
        db.execute = AsyncMock()
        db.commit = AsyncMock()

        run(route(
            "verified-tenant",
            "conv-3",
            "I am interested in your services. My name is Rayan and my email is rayan@example.com",
            [],
            db_session=db,
            llm_client=client,
        ))

        params = db.execute.call_args[0][1]
        self.assertEqual(params["tenant_id"], "verified-tenant")
        self.assertNotEqual(params["tenant_id"], "spoofed-tenant")

    def test_lead_capture_falls_back_to_public_runtime_table(self):
        client = self._make_llm_client("faq", 0.95)
        db = MagicMock()
        db.execute = AsyncMock(side_effect=[Exception("app.leads missing"), None, None])
        db.rollback = AsyncMock()
        db.commit = AsyncMock()

        result = run(route(
            "00000000-0000-0000-0000-000000000001",
            "11111111-1111-1111-1111-111111111111",
            "I want to buy. My name is Rayan and my email is rayan@example.com",
            [],
            db_session=db,
            llm_client=client,
        ))

        self.assertEqual(result.intent, "lead_capture")
        self.assertEqual(result.action, "lead_captured")
        db.rollback.assert_awaited_once()
        self.assertEqual(db.execute.await_count, 3)
        params = db.execute.await_args_list[2].args[1]
        self.assertEqual(params["tenant_id"], "00000000-0000-0000-0000-000000000001")
        self.assertEqual(params["conversation_id"], "11111111-1111-1111-1111-111111111111")
        self.assertEqual(params["email"], "rayan@example.com")

    def test_sales_missing_contact_asks_for_missing_info(self):
        client = self._make_llm_client("faq", 0.95)
        db = MagicMock()
        db.execute = AsyncMock()

        result = run(route(
            "tenant-real",
            "conv-4",
            "Can I get a quote and demo?",
            [],
            db_session=db,
            llm_client=client,
        ))

        self.assertEqual(result.intent, "lead_capture")
        self.assertIsNone(result.action)
        self.assertIn("email or phone", result.reply)
        db.execute.assert_not_called()

    def test_low_confidence_routes_to_agent(self):
        client = self._make_llm_client("faq", 0.3)  # below threshold

        async def fake_agent(**kwargs):
            return {"reply": "Let me look that up.", "action": None, "sources": []}

        result = run(route("t1", "s1", "Something unclear", [], llm_client=client, agent_fn=fake_agent))
        self.assertEqual(result.routed_to, "agent")

    def test_rag_low_confidence_falls_to_agent(self):
        """RAG answer with low confidence must escalate to agent (4A.2)."""
        client = self._make_llm_client("knowledge_search", 0.95)

        mock_rag = MagicMock()
        mock_rag.answer_from_knowledge = AsyncMock(return_value={
            "answer": "I'm not sure.",
            "sources": [],
            "confidence": 0.1,  # below RAG_CONFIDENCE_THRESHOLD
        })

        async def fake_agent(**kwargs):
            return {"reply": "Let me dig deeper for you.", "action": None, "sources": []}

        result = run(route("t1", "s1", "Tell me about your security policy?", [],
                           llm_client=client, rag_service=mock_rag, agent_fn=fake_agent))
        self.assertEqual(result.routed_to, "agent")

    def test_no_agent_returns_graceful_placeholder(self):
        """When agent_fn is None, a handoff reply is returned instead of crashing."""
        client = self._make_llm_client("lead_capture", 0.97)
        result = run(route("t1", "s1", "I'd like to talk to someone", [], llm_client=client, agent_fn=None))
        self.assertEqual(result.routed_to, "agent")
        self.assertIsNotNone(result.reply)

    def test_all_classifiers_fail_routes_to_agent(self):
        """When classification fully falls back (confidence=0.0), agent handles it."""
        result = run(route("t1", "s1", "Some message", [], llm_client=None, agent_fn=None))
        self.assertEqual(result.routed_to, "agent")
        self.assertEqual(result.intent, "knowledge_search")

    def test_route_result_fields_populated(self):
        client = self._make_llm_client("greeting", 0.98)
        result = run(route("t1", "s1", "Hey there", [], llm_client=client))
        self.assertIsInstance(result, RouteResult)
        self.assertIsInstance(result.reply, str)
        self.assertIsInstance(result.intent, str)
        self.assertIsInstance(result.confidence, float)
        self.assertIsInstance(result.sources, list)


# ---------------------------------------------------------------------------
# Logging tests (4A.3)
# ---------------------------------------------------------------------------


class TestLogging(unittest.TestCase):

    def test_log_routing_emits_all_required_fields(self):
        cr = ClassifyResult(intent="faq", confidence=0.9, source="llm")
        with self.assertLogs("services.router.router", level="INFO") as cm:
            _log_routing("tenant-abc", "sess-123", "What are your hours?", cr, "rag")

        log_line = cm.output[0]
        self.assertIn("tenant=tenant-abc", log_line)
        self.assertIn("session=sess-123", log_line)
        self.assertIn("intent=faq", log_line)
        self.assertIn("routed_to=rag", log_line)
        self.assertIn("classifier_source=llm", log_line)
        # msg_hash should be a 16-char hex string
        expected_hash = hashlib.sha256("What are your hours?".encode()).hexdigest()[:16]
        self.assertIn(f"msg_hash={expected_hash}", log_line)

    def test_message_hash_is_16_hex_chars(self):
        cr = ClassifyResult(intent="greeting", confidence=0.98, source="llm")
        with self.assertLogs("services.router.router", level="INFO") as cm:
            _log_routing("t", "s", "Hello!", cr, "direct")

        log_line = cm.output[0]
        import re
        match = re.search(r"msg_hash=([0-9a-f]+)", log_line)
        self.assertIsNotNone(match)
        self.assertEqual(len(match.group(1)), 16)


if __name__ == "__main__":
    unittest.main()
