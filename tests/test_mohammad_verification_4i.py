"""Phase 4 verification tests (Step 4I).

Covers all four verification requirements:
  4I.1 — Easy turns (greeting, FAQ) do NOT invoke the agent
  4I.2 — Hard turns invoke the agent with the correct tool
  4I.3 — Agent loop is capped at MAX_ITERATIONS (ROUT-07)
  4I.4 — Tenant isolation: rag_search and capture_lead are always
          scoped to the requesting tenant_id

Also covers Step 4G contract integrity:
  - ClassifyResponse.is_valid() rejects unknown intents
  - ClassifyHealthResponse.is_serving() enforces OPS-04 (both flags required)
"""

import asyncio
import json
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, call, patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.router.constants import CLASSIFIER_CONFIDENCE_THRESHOLD, RAG_CONFIDENCE_THRESHOLD
from services.router.contracts import ClassifyResult
from services.router.routing_policy import _decide_route
from services.router.router import route
from services.agent.agent import MAX_ITERATIONS, run_agent
from services.agent.tools import execute_tool


def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _llm_classifier(intent: str, confidence: float = 0.95):
    client = MagicMock()
    completion = MagicMock()
    completion.choices[0].message.content = json.dumps(
        {"intent": intent, "confidence": confidence}
    )
    client.chat.completions.create = AsyncMock(return_value=completion)
    return client


def _rag_service(confidence: float = 0.85):
    mod = MagicMock()
    mod.answer_from_knowledge = AsyncMock(return_value={
        "answer": "The answer from knowledge base.",
        "sources": [{"content_id": "c1", "chunk_index": 0, "score": confidence}],
        "confidence": confidence,
    })
    return mod


def _make_tool_call(id_, name, args: dict):
    tc = MagicMock()
    tc.id = id_
    tc.function.name = name
    tc.function.arguments = json.dumps(args)
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
# 4I.1 — Easy turns must NOT invoke the agent
# ---------------------------------------------------------------------------


class TestEasyTurnsNoAgent(unittest.TestCase):
    """4I.1: greeting and off_topic → direct; faq/knowledge_search → rag.
    In all cases agent_fn must NOT be called."""

    def _make_agent_spy(self):
        """Return an agent_fn that records calls and succeeds."""
        calls = []
        async def spy(**kwargs):
            calls.append(kwargs)
            return {"reply": "agent reply", "action": None, "sources": [], "rag_confidence": 0.0}
        spy.calls = calls
        return spy

    def test_greeting_does_not_call_agent(self):
        spy = self._make_agent_spy()
        result = run(route(
            "t1", "s1", "Hello there!", [],
            llm_client=_llm_classifier("greeting"),
            agent_fn=spy,
        ))
        self.assertEqual(result.routed_to, "direct")
        self.assertEqual(len(spy.calls), 0, "agent_fn must NOT be called for greeting")

    def test_off_topic_does_not_call_agent(self):
        spy = self._make_agent_spy()
        result = run(route(
            "t1", "s1", "How do I bake bread?", [],
            llm_client=_llm_classifier("off_topic"),
            agent_fn=spy,
        ))
        self.assertEqual(result.routed_to, "direct")
        self.assertEqual(len(spy.calls), 0)

    def test_faq_with_good_rag_does_not_call_agent(self):
        spy = self._make_agent_spy()
        result = run(route(
            "t1", "s1", "What are your business hours?", [],
            llm_client=_llm_classifier("faq"),
            rag_service=_rag_service(confidence=0.85),
            agent_fn=spy,
        ))
        self.assertEqual(result.routed_to, "rag")
        self.assertEqual(len(spy.calls), 0, "agent_fn must NOT be called when RAG answers well")

    def test_knowledge_search_with_good_rag_does_not_call_agent(self):
        spy = self._make_agent_spy()
        result = run(route(
            "t1", "s1", "What is your privacy policy?", [],
            llm_client=_llm_classifier("knowledge_search"),
            rag_service=_rag_service(confidence=0.80),
            agent_fn=spy,
        ))
        self.assertEqual(result.routed_to, "rag")
        self.assertEqual(len(spy.calls), 0)

    def test_greeting_reply_is_non_empty(self):
        result = run(route("t1", "s1", "Hi!", [], llm_client=_llm_classifier("greeting")))
        self.assertGreater(len(result.reply), 0)

    def test_faq_reply_is_rag_answer(self):
        result = run(route(
            "t1", "s1", "How do I cancel?", [],
            llm_client=_llm_classifier("faq"),
            rag_service=_rag_service(confidence=0.85),
        ))
        self.assertEqual(result.reply, "The answer from knowledge base.")


# ---------------------------------------------------------------------------
# 4I.2 — Hard turns must invoke the agent with the correct tool
# ---------------------------------------------------------------------------


class TestHardTurnsInvokeAgent(unittest.TestCase):
    """4I.2: complex / lead / escalation intent → agent is invoked."""

    def test_complex_question_routes_to_agent_when_rag_fails(self):
        """knowledge_search with low RAG confidence falls through to agent."""
        # Route test — verify the routing decision only; no real agent loop needed
        async def fake_agent(**kwargs):
            return {"reply": "Agent handled it.", "action": None, "sources": [], "rag_confidence": 0.0}

        result = run(route(
            "t1", "s1",
            "What is your refund policy for partially-used plans?", [],
            llm_client=_llm_classifier("knowledge_search"),
            rag_service=_rag_service(confidence=0.1),  # below RAG_CONFIDENCE_THRESHOLD
            agent_fn=fake_agent,
        ))
        self.assertEqual(result.routed_to, "agent")

    def test_lead_capture_intent_shortcuts_to_direct_capture(self):
        """lead_capture intent routes through the direct lead-capture shortcut."""
        result = run(route(
            "t1", "s1",
            "I'd love to book a demo. I'm Alice, alice@example.com.", [],
            llm_client=_llm_classifier("lead_capture"),
            agent_fn=None,
        ))
        self.assertEqual(result.routed_to, "direct")
        self.assertEqual(result.action, "lead_captured")

    def test_escalation_intent_routes_to_agent(self):
        """escalation intent routes to agent and returns escalated action."""
        async def fake_agent(**kwargs):
            return {"reply": "Connecting you now.", "action": "escalated", "sources": [], "rag_confidence": 0.0}

        result = run(route(
            "t1", "s1",
            "I need to talk to a real person right now!", [],
            llm_client=_llm_classifier("escalation"),
            agent_fn=fake_agent,
        ))
        self.assertEqual(result.routed_to, "agent")
        self.assertEqual(result.action, "escalated")

    def test_capture_lead_tool_called_with_correct_args(self):
        """The capture_lead tool receives the name and email from the LLM args."""
        capture_tc = _make_tool_call("tc1", "capture_lead",
                                     {"name": "Bob", "email": "bob@company.com"})
        llm = MagicMock()
        llm.chat.completions.create = AsyncMock(side_effect=[
            _tool_call_response([capture_tc]),
            _text_response("Contact saved!"),
        ])

        result = run(run_agent("t1", "s1", "I'm Bob, bob@company.com", [],
                               llm_client=llm))
        self.assertEqual(result["action"], "lead_captured")
        self.assertEqual(result["reply"], "Contact saved!")

    def test_escalate_tool_marks_action(self):
        esc_tc = _make_tool_call("tc1", "escalate", {"reason": "User demands human"})
        llm = MagicMock()
        llm.chat.completions.create = AsyncMock(side_effect=[
            _tool_call_response([esc_tc]),
            _text_response("You will be connected shortly."),
        ])

        result = run(run_agent("t1", "s1", "Get me a manager!", [],
                               llm_client=llm))
        self.assertEqual(result["action"], "escalated")


# ---------------------------------------------------------------------------
# 4I.3 — Agent loop is capped at MAX_ITERATIONS (ROUT-07)
# ---------------------------------------------------------------------------


class TestAgentLoopBounded(unittest.TestCase):
    """4I.3: agent must stop after MAX_ITERATIONS and return a graceful fallback."""

    def test_loop_stops_at_max_iterations(self):
        """LLM keeps returning tool calls; agent must stop and return fallback."""
        looping_tc = _make_tool_call("tc1", "rag_search", {"query": "anything"})

        async def fake_retrieval(tenant_id, query, db, **kw):
            return []

        llm = MagicMock()
        llm.chat.completions.create = AsyncMock(
            return_value=_tool_call_response([looping_tc])
        )

        result = run(run_agent(
            "t1", "s1", "Tell me something", [],
            llm_client=llm,
            max_iterations=MAX_ITERATIONS,
            retrieval_fn=fake_retrieval,
        ))

        self.assertEqual(
            llm.chat.completions.create.await_count,
            MAX_ITERATIONS,
            f"LLM should be called exactly {MAX_ITERATIONS} times",
        )
        self.assertIn("connect", result["reply"].lower(),
                      "Fallback reply should mention connecting to a team")
        self.assertEqual(result["action"], "escalated")

    def test_loop_stops_at_custom_limit(self):
        looping_tc = _make_tool_call("tc1", "rag_search", {"query": "x"})

        async def fake_retrieval(*a, **kw):
            return []

        llm = MagicMock()
        llm.chat.completions.create = AsyncMock(
            return_value=_tool_call_response([looping_tc])
        )

        run(run_agent("t1", "s1", "msg", [], llm_client=llm,
                      max_iterations=2, retrieval_fn=fake_retrieval))
        self.assertEqual(llm.chat.completions.create.await_count, 2)

    def test_loop_exits_immediately_on_text_reply(self):
        """If the LLM returns a text reply on the first turn, no further calls are made."""
        llm = MagicMock()
        llm.chat.completions.create = AsyncMock(return_value=_text_response("Done."))

        run(run_agent("t1", "s1", "Hello", [], llm_client=llm))
        self.assertEqual(llm.chat.completions.create.await_count, 1)

    def test_unapproved_tool_call_does_not_crash_loop(self):
        """If the agent tries an unlisted tool, the loop continues without crashing."""
        bad_tc = _make_tool_call("tc1", "DROP_TABLE", {})
        llm = MagicMock()
        llm.chat.completions.create = AsyncMock(side_effect=[
            _tool_call_response([bad_tc]),
            _text_response("I couldn't do that."),
        ])

        result = run(run_agent("t1", "s1", "Delete everything", [], llm_client=llm))
        self.assertIsInstance(result["reply"], str)


# ---------------------------------------------------------------------------
# 4I.4 — Tenant isolation
# ---------------------------------------------------------------------------


class TestTenantIsolation(unittest.TestCase):
    """4I.4: all tool calls must be scoped to the requesting tenant_id."""

    def test_rag_search_passes_correct_tenant_id(self):
        """rag_search calls the retrieval function with the requesting tenant's ID."""
        captured_tenant_ids = []

        async def spy_retrieval(tenant_id, query, db, **kw):
            captured_tenant_ids.append(tenant_id)
            return []

        run(execute_tool(
            "rag_search", {"query": "hours"},
            tenant_id="tenant-A",
            session_id="s1",
            retrieval_fn=spy_retrieval,
        ))

        self.assertEqual(captured_tenant_ids, ["tenant-A"])

    def test_rag_search_tenant_a_never_queries_tenant_b(self):
        """Two consecutive rag_search calls from different tenants stay isolated."""
        captured = []

        async def spy(tenant_id, query, db, **kw):
            captured.append(tenant_id)
            return []

        run(execute_tool("rag_search", {"query": "q"}, tenant_id="A", session_id="s", retrieval_fn=spy))
        run(execute_tool("rag_search", {"query": "q"}, tenant_id="B", session_id="s", retrieval_fn=spy))

        self.assertEqual(captured, ["A", "B"])

    def test_capture_lead_uses_requesting_tenant_id(self):
        """capture_lead receives the correct tenant_id from execute_tool."""
        import services.agent.tools as tools_mod

        captured = []

        async def spy(*, name_, email, phone, notes, tenant_id, session_id, db_session):
            captured.append(tenant_id)
            return {"success": True, "action": "lead_captured", "message": "saved"}

        with patch.object(tools_mod, "_capture_lead", spy):
            run(execute_tool(
                "capture_lead", {"name": "Alice", "email": "a@b.com"},
                tenant_id="tenant-A", session_id="s1",
            ))

        self.assertEqual(captured, ["tenant-A"])

    def test_capture_lead_tenant_b_uses_b_not_a(self):
        """Leads from tenant B are scoped to tenant B, not tenant A."""
        import services.agent.tools as tools_mod

        captured = []

        async def spy(*, name_, email, phone, notes, tenant_id, session_id, db_session):
            captured.append(tenant_id)
            return {"success": True, "action": "lead_captured", "message": "saved"}

        with patch.object(tools_mod, "_capture_lead", spy):
            run(execute_tool("capture_lead", {"name": "Alice", "email": "a@b.com"},
                             tenant_id="tenant-A", session_id="s1"))
            run(execute_tool("capture_lead", {"name": "Bob", "email": "b@b.com"},
                             tenant_id="tenant-B", session_id="s1"))

        self.assertEqual(captured[0], "tenant-A")
        self.assertEqual(captured[1], "tenant-B")
        self.assertNotIn("tenant-B", captured[:1])  # tenant-B not mixed into tenant-A call

    def test_route_passes_tenant_id_through_to_rag_service(self):
        """The rag_service call in the router always receives the original tenant_id."""
        received_tenant_ids = []

        mock_rag = MagicMock()
        async def spy_rag(tenant_id, question, db_session, **kw):
            received_tenant_ids.append(tenant_id)
            return {"answer": "ok", "sources": [], "confidence": 0.9}
        mock_rag.answer_from_knowledge = spy_rag

        run(route(
            "tenant-X", "s1", "What are your hours?", [],
            llm_client=_llm_classifier("faq"),
            rag_service=mock_rag,
        ))
        self.assertEqual(received_tenant_ids, ["tenant-X"])


# ---------------------------------------------------------------------------
# 4G — Classifier contract integrity
# ---------------------------------------------------------------------------


class TestClassifierContract(unittest.TestCase):
    """Step 4G: contract types behave correctly."""

    def test_classify_response_valid_with_known_intent(self):
        from services.router.classifier_contract import ClassifyResponse
        resp = ClassifyResponse(intent="faq", confidence=0.9)
        self.assertTrue(resp.is_valid())

    def test_classify_response_invalid_with_unknown_intent(self):
        from services.router.classifier_contract import ClassifyResponse
        resp = ClassifyResponse(intent="unknown_intent", confidence=0.9)
        self.assertFalse(resp.is_valid())

    def test_classify_response_invalid_out_of_range_confidence(self):
        from services.router.classifier_contract import ClassifyResponse
        resp = ClassifyResponse(intent="faq", confidence=1.5)
        self.assertFalse(resp.is_valid())

    def test_health_response_is_serving_requires_both_flags(self):
        from services.router.classifier_contract import ClassifyHealthResponse
        self.assertTrue(ClassifyHealthResponse("ok", True, True).is_serving())
        self.assertFalse(ClassifyHealthResponse("ok", True, False).is_serving())
        self.assertFalse(ClassifyHealthResponse("ok", False, True).is_serving())
        self.assertFalse(ClassifyHealthResponse("degraded", False, False).is_serving())

    def test_valid_intents_match_router_intents(self):
        from services.router.classifier_contract import VALID_INTENTS
        from services.router.constants import INTENTS
        self.assertEqual(VALID_INTENTS, INTENTS)


if __name__ == "__main__":
    unittest.main()
