"""Intent routing decisions.

Mohammad owns the router-first / agent-second policy.
Rayan owns the classifier quality that feeds the router.
"""

import logging
from typing import Callable, Dict, List, Optional

from services.router.classifier_client import normalize_classifier_intent
from services.router.classifier_service import classify_intent
from services.router.constants import (
    CLASSIFIER_CONFIDENCE_THRESHOLD,
    INTENTS,
    RAG_CONFIDENCE_THRESHOLD,
    _DIRECT_REPLIES,
)
from services.router.contracts import ClassifyResult, RouteResult
from services.router.lead_capture import _capture_lead_direct
from services.router.lead_utils import _has_contact_info, _has_sales_signal
from services.router.routing_logging import _log_routing
from services.router.routing_policy import _decide_route
from services.tracing import span

logger = logging.getLogger(__name__)


async def route(
    tenant_id: str,
    session_id: str,
    message: str,
    conversation_history: List[Dict],
    db_session=None,
    redis_client=None,
    llm_client=None,
    classifier_url: Optional[str] = None,
    agent_fn: Optional[Callable] = None,
    rag_service=None,
) -> RouteResult:
    """
    Route an inbound message to the appropriate handler.

    Parameters
    ----------
    tenant_id : str
        Identifies the knowledge base and lead storage scope.
    session_id : str
        Conversation session - used in routing logs.
    message : str
        The visitor's current message.
    conversation_history : list[dict]
        Recent turns in the form [{"role": "user"|"assistant", "content": "..."}].
    db_session :
        Async SQLAlchemy session (required for RAG path).
    redis_client :
        Optional Redis client for embedding cache.
    llm_client :
        OpenAI-compatible async client (used for LLM fallback classifier and RAG).
    classifier_url : str | None
        Base URL of Rayan's model server (e.g. "http://model-server:8001").
        When None, falls back to LLM classification.
    agent_fn : async callable | None
        The agent orchestrator (implemented in Phase 4B).
        Signature: async (tenant_id, session_id, message, conversation_history,
                          intent, db_session, redis_client, llm_client) -> dict
    rag_service :
        Module or object exposing ``answer_from_knowledge()``.
        Defaults to ``apps.api.app.services.rag_service`` when None.

    Returns
    -------
    RouteResult
    """
    with span("router.classify", tenant_id=tenant_id, session_id=session_id) as s:
        classification = await classify_intent(
            tenant_id, message, conversation_history, classifier_url, llm_client
        )
        s.set_attribute("intent", classification.intent)
        s.set_attribute("confidence", str(classification.confidence))
        s.set_attribute("source", classification.source)

    routed_to = _decide_route(classification)
    _log_routing(tenant_id, session_id, message, classification, routed_to)

    if routed_to == "direct":
        reply = _DIRECT_REPLIES.get(
            classification.intent,
            "How can I assist you today?",
        )
        return RouteResult(
            reply=reply,
            intent=classification.intent,
            confidence=classification.confidence,
            routed_to="direct",
            action=None,
        )

    if classification.intent == "lead_capture" and (
        _has_sales_signal(message)
        or _has_contact_info(message)
        or classification.raw_intent == "sales_or_leads"
    ):
        lead_result = await _capture_lead_direct(
            tenant_id=tenant_id,
            session_id=session_id,
            message=message,
            db_session=db_session,
        )
        return RouteResult(
            reply=lead_result.get("reply", ""),
            intent=classification.intent,
            confidence=classification.confidence,
            routed_to="direct",
            action=lead_result.get("action"),
        )

    if routed_to == "rag":
        rag_mod = rag_service
        if rag_mod is None:
            from apps.api.app.services import rag_service as _default_rag
            rag_mod = _default_rag

        rag_result = await rag_mod.answer_from_knowledge(
            tenant_id=tenant_id,
            question=message,
            db_session=db_session,
            redis_client=redis_client,
            llm_client=llm_client,
        )

        rag_confidence = float(rag_result.get("confidence", 0.0))

        if rag_confidence < RAG_CONFIDENCE_THRESHOLD and agent_fn is not None:
            logger.info(
                "RAG confidence %.3f below %.3f for tenant=%s; escalating to agent",
                rag_confidence,
                RAG_CONFIDENCE_THRESHOLD,
                tenant_id,
            )
            routed_to = "agent"
        else:
            return RouteResult(
                reply=rag_result.get("answer", ""),
                intent=classification.intent,
                confidence=classification.confidence,
                routed_to="rag",
                action=None,
                sources=rag_result.get("sources", []),
                rag_confidence=rag_confidence,
            )

    if agent_fn is not None:
        agent_result = await agent_fn(
            tenant_id=tenant_id,
            session_id=session_id,
            message=message,
            conversation_history=conversation_history,
            intent=classification.intent,
            db_session=db_session,
            redis_client=redis_client,
            llm_client=llm_client,
        )
        return RouteResult(
            reply=agent_result.get("reply", ""),
            intent=classification.intent,
            confidence=classification.confidence,
            routed_to="agent",
            action=agent_result.get("action"),
            sources=agent_result.get("sources", []),
            rag_confidence=agent_result.get("rag_confidence", 0.0),
        )

    logger.warning(
        "Agent not wired for tenant=%s session=%s; returning handoff reply",
        tenant_id,
        session_id,
    )
    return RouteResult(
        reply=(
            "I'd like to help you further. "
            "Let me connect you with a member of our team who can assist you."
        ),
        intent=classification.intent,
        confidence=classification.confidence,
        routed_to="agent",
        action=None,
    )


__all__ = [
    "CLASSIFIER_CONFIDENCE_THRESHOLD",
    "INTENTS",
    "RAG_CONFIDENCE_THRESHOLD",
    "ClassifyResult",
    "RouteResult",
    "_capture_lead_direct",
    "_decide_route",
    "_log_routing",
    "classify_intent",
    "normalize_classifier_intent",
    "route",
]
