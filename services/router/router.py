"""Intent routing decisions.

Mohammad owns the router-first / agent-second policy.
Rayan owns the classifier quality that feeds the router.
"""

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from apps.shared.service_auth import get_service_token
from services.tracing import span

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

INTENTS = frozenset({"greeting", "faq", "knowledge_search", "lead_capture", "escalation", "off_topic"})

# Below this classifier confidence → always route to agent (4A.2)
CLASSIFIER_CONFIDENCE_THRESHOLD = 0.7

# Below this RAG answer confidence → fall through to agent (4A.2)
RAG_CONFIDENCE_THRESHOLD = 0.5

_DIRECT_REPLIES: Dict[str, str] = {
    "greeting": "Hello! How can I help you today?",
    "off_topic": (
        "I'm here to help with questions about our products and services. "
        "Is there anything I can assist you with in that area?"
    ),
}

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class ClassifyResult:
    intent: str
    confidence: float
    source: str  # "classifier_server" | "llm" | "fallback"


@dataclass
class RouteResult:
    reply: str
    intent: str
    confidence: float
    routed_to: str              # "direct" | "rag" | "agent"
    action: Optional[str]       # None | "lead_captured" | "escalated"
    sources: List[Dict[str, Any]] = field(default_factory=list)
    rag_confidence: float = 0.0


# ---------------------------------------------------------------------------
# Intent classification helpers (4A.1)
# ---------------------------------------------------------------------------


async def _call_classifier_server(
    tenant_id: str,
    message: str,
    classifier_url: str,
) -> Optional[ClassifyResult]:
    """Call Rayan's model server POST /classify. Returns None if unavailable."""
    try:
        import httpx

        service_token = get_service_token()
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.post(
                f"{classifier_url.rstrip('/')}/classify",
                headers={"Authorization": f"Bearer {service_token}"},
                json={"tenant_id": tenant_id, "message": message},
            )
            resp.raise_for_status()
            data = resp.json()

        intent = str(data.get("intent", "")).lower()
        confidence = float(data.get("confidence", 0.0))

        if intent not in INTENTS:
            logger.warning("Classifier server returned unknown intent '%s'", intent)
            return None

        return ClassifyResult(intent=intent, confidence=confidence, source="classifier_server")

    except Exception as exc:
        logger.warning("Classifier server unavailable (%s); falling back to LLM", exc)
        return None


async def _classify_via_llm(
    message: str,
    conversation_history: List[Dict],
    llm_client,
) -> Optional[ClassifyResult]:
    """Classify using the intent_classifier prompt + LLM when the model server is down."""
    try:
        prompt_path = os.path.normpath(
            os.path.join(
                os.path.dirname(__file__),
                "..", "..", "prompts", "router", "intent_classifier.md",
            )
        )
        with open(prompt_path) as f:
            system_prompt = f.read()

        # Include up to 4 recent turns as context so classification is history-aware
        history_context = ""
        if conversation_history:
            recent = conversation_history[-4:]
            history_context = "\n".join(
                f"{m.get('role', 'user').capitalize()}: {m.get('content', '')}"
                for m in recent
            )

        user_content = (
            f"Conversation so far:\n{history_context}\n\nNew message: {message}"
            if history_context
            else message
        )

        response = await llm_client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=0.0,
            max_tokens=64,
        )

        raw = response.choices[0].message.content.strip()
        data = json.loads(raw)
        intent = str(data.get("intent", "")).lower()
        confidence = float(data.get("confidence", 0.0))

        if intent not in INTENTS:
            logger.warning("LLM classifier returned unknown intent '%s'", intent)
            return None

        return ClassifyResult(intent=intent, confidence=confidence, source="llm")

    except Exception as exc:
        logger.error("LLM classification failed: %s", exc)
        return None


async def classify_intent(
    tenant_id: str,
    message: str,
    conversation_history: List[Dict],
    classifier_url: Optional[str],
    llm_client,
) -> ClassifyResult:
    """
    Classify the intent of *message*.

    Resolution order:
    1. Rayan's model server (if classifier_url is set).
    2. LLM with the intent_classifier prompt (if llm_client is set).
    3. Fallback to knowledge_search with 0.0 confidence → agent handles it.
    """
    if classifier_url:
        result = await _call_classifier_server(tenant_id, message, classifier_url)
        if result:
            return result

    if llm_client:
        result = await _classify_via_llm(message, conversation_history, llm_client)
        if result:
            return result

    logger.warning("All classifiers failed; defaulting to knowledge_search with 0.0 confidence")
    return ClassifyResult(intent="knowledge_search", confidence=0.0, source="fallback")


# ---------------------------------------------------------------------------
# Routing logic (4A.1, 4A.2)
# ---------------------------------------------------------------------------


def _decide_route(classification: ClassifyResult) -> str:
    """
    Map intent + confidence to a route string.

    Rules (ROUT-01..03):
    - Low confidence → agent (fallback handles anything uncertain)
    - greeting / off_topic → direct (no LLM call needed)
    - faq / knowledge_search → rag
    - lead_capture / escalation → agent
    """
    if classification.confidence < CLASSIFIER_CONFIDENCE_THRESHOLD:
        return "agent"

    if classification.intent in ("greeting", "off_topic"):
        return "direct"

    if classification.intent in ("faq", "knowledge_search"):
        return "rag"

    if classification.intent in ("lead_capture", "escalation"):
        return "agent"

    return "agent"


# ---------------------------------------------------------------------------
# Logging (4A.3)
# ---------------------------------------------------------------------------


def _log_routing(
    tenant_id: str,
    session_id: str,
    message: str,
    classification: ClassifyResult,
    routed_to: str,
) -> None:
    message_hash = hashlib.sha256(message.encode()).hexdigest()[:16]
    logger.info(
        "ROUTING_DECISION tenant=%s session=%s msg_hash=%s intent=%s "
        "confidence=%.3f routed_to=%s classifier_source=%s",
        tenant_id,
        session_id,
        message_hash,
        classification.intent,
        classification.confidence,
        routed_to,
        classification.source,
    )


# ---------------------------------------------------------------------------
# Main entry point (4A.1, 4A.2, 4A.3)
# ---------------------------------------------------------------------------


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
        Conversation session — used in routing logs.
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
    # 1. Classify --------------------------------------------------------
    with span("router.classify", tenant_id=tenant_id, session_id=session_id) as s:
        classification = await classify_intent(
            tenant_id, message, conversation_history, classifier_url, llm_client
        )
        s.set_attribute("intent", classification.intent)
        s.set_attribute("confidence", str(classification.confidence))
        s.set_attribute("source", classification.source)

    # 2. Decide route ----------------------------------------------------
    routed_to = _decide_route(classification)
    _log_routing(tenant_id, session_id, message, classification, routed_to)

    # 3a. Direct answer (greeting / off_topic) ---------------------------
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

    # 3b. RAG path (faq / knowledge_search) ------------------------------
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

        # 4. RAG confidence fallback → agent (4A.2) ----------------------
        if rag_confidence < RAG_CONFIDENCE_THRESHOLD and agent_fn is not None:
            logger.info(
                "RAG confidence %.3f below %.3f for tenant=%s; escalating to agent",
                rag_confidence,
                RAG_CONFIDENCE_THRESHOLD,
                tenant_id,
            )
            routed_to = "agent"
            # fall through to agent block below
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

    # 3c. Agent path (lead_capture / escalation / low-confidence / RAG fallback)
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

    # Agent not yet wired (Phase 4B pending) — graceful placeholder
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
