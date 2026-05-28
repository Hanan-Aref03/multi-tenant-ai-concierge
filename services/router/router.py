"""Intent routing decisions.

Mohammad owns the router-first / agent-second policy.
Rayan owns the classifier quality that feeds the router.
"""

import hashlib
import json
import logging
import os
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from apps.shared.service_auth import get_service_token
from apps.shared.llm_client import get_chat_model
from services.tracing import span

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

INTENTS = frozenset({"greeting", "faq", "knowledge_search", "lead_capture", "escalation", "off_topic", "spam"})

MODELSERVER_INTENT_MAP: Dict[str, str] = {
    "faq": "faq",
    "support": "knowledge_search",
    "sales_or_leads": "lead_capture",
    "human_request": "escalation",
    "spam": "spam",
    "other": "knowledge_search",
}

# Below this classifier confidence → always route to agent (4A.2)
CLASSIFIER_CONFIDENCE_THRESHOLD = 0.7

# Below this RAG answer confidence → fall through to agent (4A.2)
RAG_CONFIDENCE_THRESHOLD = 0.5

SALES_KEYWORDS = (
    "pricing",
    "buy",
    "interested",
    "contact me",
    "sales representative",
    "my email is",
    "my name is",
    "quote",
    "demo",
)

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")
NAME_RE = re.compile(
    r"\bmy name is\s+([A-Z][A-Za-z.'-]*(?:\s+[A-Z][A-Za-z.'-]*){0,3})",
    re.IGNORECASE,
)

_DIRECT_REPLIES: Dict[str, str] = {
    "greeting": "Hello! How can I help you today?",
    "spam": "I can't help with that request. If you need help with our products or services, please send a clear question.",
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
    raw_intent: Optional[str] = None
    raw_route: Optional[str] = None


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


def normalize_classifier_intent(label: str) -> str:
    """Map modelserver labels onto router-owned intent names in one place."""
    normalized = str(label or "").strip().lower()
    return MODELSERVER_INTENT_MAP.get(normalized, normalized)


def _has_sales_signal(message: str) -> bool:
    lowered = message.lower()
    return any(keyword in lowered for keyword in SALES_KEYWORDS)


def _extract_contact(message: str) -> Dict[str, Optional[str]]:
    email_match = EMAIL_RE.search(message)
    phone_match = PHONE_RE.search(message)
    name_match = NAME_RE.search(message)
    name = None
    if name_match:
        name = re.split(
            r"\s+(?:and|email|phone|at|contact)\b",
            name_match.group(1).strip(" .,!?:;"),
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0].strip(" .,!?:;")
    return {
        "name": name,
        "email": email_match.group(0) if email_match else None,
        "phone": phone_match.group(0).strip() if phone_match else None,
    }


def _has_contact_info(message: str) -> bool:
    contact = _extract_contact(message)
    return bool(contact["email"] or contact["phone"])


def _should_force_lead_capture(message: str, classification: ClassifyResult) -> bool:
    if classification.intent == "lead_capture":
        return True
    if not _has_sales_signal(message):
        return False
    return (
        classification.intent in {"knowledge_search", "faq", "escalation"}
        or classification.confidence < CLASSIFIER_CONFIDENCE_THRESHOLD
    )


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

        raw_intent = str(data.get("intent", "")).lower()
        raw_route = str(data.get("route", "")).lower()
        intent = normalize_classifier_intent(raw_intent)
        confidence = float(data.get("confidence", 0.0))

        logger.info(
            "CLASSIFIER_RESULT tenant=%s raw_intent=%s raw_route=%s normalized_intent=%s confidence=%.3f",
            tenant_id,
            raw_intent,
            raw_route,
            intent,
            confidence,
        )

        if intent not in INTENTS:
            logger.warning("Classifier server returned unknown intent '%s'", raw_intent)
            return None

        return ClassifyResult(
            intent=intent,
            confidence=confidence,
            source="classifier_server",
            raw_intent=raw_intent,
            raw_route=raw_route,
        )

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
            model=get_chat_model(),
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

        return ClassifyResult(intent=intent, confidence=confidence, source="llm", raw_intent=intent)

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
            if _should_force_lead_capture(message, result):
                logger.info(
                    "LEAD_KEYWORD_FALLBACK tenant=%s original_intent=%s raw_intent=%s confidence=%.3f",
                    tenant_id,
                    result.intent,
                    result.raw_intent,
                    result.confidence,
                )
                return ClassifyResult(
                    intent="lead_capture",
                    confidence=max(result.confidence, CLASSIFIER_CONFIDENCE_THRESHOLD),
                    source=f"{result.source}:keyword_fallback",
                    raw_intent=result.raw_intent,
                    raw_route=result.raw_route,
                )
            return result

    if llm_client:
        result = await _classify_via_llm(message, conversation_history, llm_client)
        if result:
            if _should_force_lead_capture(message, result):
                logger.info(
                    "LEAD_KEYWORD_FALLBACK tenant=%s original_intent=%s raw_intent=%s confidence=%.3f",
                    tenant_id,
                    result.intent,
                    result.raw_intent,
                    result.confidence,
                )
                return ClassifyResult(
                    intent="lead_capture",
                    confidence=max(result.confidence, CLASSIFIER_CONFIDENCE_THRESHOLD),
                    source=f"{result.source}:keyword_fallback",
                    raw_intent=result.raw_intent,
                    raw_route=result.raw_route,
                )
            return result

    logger.warning("All classifiers failed; defaulting to knowledge_search with 0.0 confidence")
    fallback = ClassifyResult(intent="knowledge_search", confidence=0.0, source="fallback")
    if _should_force_lead_capture(message, fallback):
        return ClassifyResult(
            intent="lead_capture",
            confidence=CLASSIFIER_CONFIDENCE_THRESHOLD,
            source="fallback:keyword_fallback",
        )
    return fallback


# ---------------------------------------------------------------------------
# Routing logic (4A.1, 4A.2)
# ---------------------------------------------------------------------------


def _decide_route(classification: ClassifyResult) -> str:
    """
    Map intent + confidence to a route string.

    Rules (ROUT-01..03):
    - Low confidence → agent (fallback handles anything uncertain)
    - greeting / off_topic / spam → direct (no LLM call needed)
    - faq / knowledge_search → rag
    - lead_capture / escalation → agent
    """
    if classification.confidence < CLASSIFIER_CONFIDENCE_THRESHOLD:
        return "agent"

    if classification.intent in ("greeting", "off_topic", "spam"):
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
        "confidence=%.3f routed_to=%s classifier_source=%s raw_intent=%s raw_route=%s",
        tenant_id,
        session_id,
        message_hash,
        classification.intent,
        classification.confidence,
        routed_to,
        classification.source,
        classification.raw_intent,
        classification.raw_route,
    )


async def _capture_lead_direct(
    *,
    tenant_id: str,
    session_id: str,
    message: str,
    db_session,
) -> Dict[str, Any]:
    contact = _extract_contact(message)
    name = contact["name"] or "there"
    email = contact["email"]
    phone = contact["phone"]

    missing = []
    if not email and not phone:
        missing.append("email or phone number")
    if missing:
        return {
            "reply": f"I can help with that. Please share your {' and '.join(missing)} so our team can contact you.",
            "action": None,
        }

    if db_session is not None:
        try:
            from sqlalchemy import text as sa_text

            lead_id = str(uuid.uuid4())
            params = {
                "lead_id": lead_id,
                "tenant_id": tenant_id,
                "conversation_id": session_id,
                "full_name": contact["name"] or "Website visitor",
                "email": email or "",
                "phone": phone,
                "message": message,
                "metadata": json.dumps({
                    "phone": phone,
                    "conversation_id": session_id,
                    "intent": "lead_capture",
                    "message": message,
                }),
            }
            try:
                await db_session.execute(
                    sa_text("""
                        INSERT INTO app.leads
                            (lead_id, tenant_id, full_name, email, intent, source, status, metadata, created_at)
                        VALUES
                            (:lead_id, :tenant_id, :full_name, :email, 'sales_or_leads',
                             'widget', 'new', :metadata, NOW());
                    """),
                    params,
                )
            except Exception:
                if hasattr(db_session, "rollback"):
                    await db_session.rollback()
                await db_session.execute(
                    sa_text("""
                        CREATE TABLE IF NOT EXISTS public.leads (
                            lead_id uuid PRIMARY KEY,
                            tenant_id uuid NOT NULL,
                            conversation_id uuid NOT NULL,
                            full_name text NOT NULL,
                            email text NOT NULL,
                            phone text,
                            intent text NOT NULL,
                            message text NOT NULL,
                            source text NOT NULL DEFAULT 'widget',
                            status text NOT NULL DEFAULT 'new',
                            metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
                            created_at timestamptz NOT NULL DEFAULT now()
                        );
                    """)
                )
                await db_session.execute(
                    sa_text("""
                        INSERT INTO public.leads
                            (lead_id, tenant_id, conversation_id, full_name, email, phone,
                             intent, message, source, status, metadata, created_at)
                        VALUES
                            (:lead_id, :tenant_id, :conversation_id, :full_name, :email, :phone,
                             'sales_or_leads', :message, 'widget', 'new', :metadata, NOW());
                    """),
                    params,
                )
            if hasattr(db_session, "commit"):
                await db_session.commit()
            logger.info("Lead captured directly: tenant=%s session=%s lead_id=%s", tenant_id, session_id, lead_id)
        except Exception as exc:
            logger.error("Direct lead capture failed for tenant=%s session=%s: %s", tenant_id, session_id, exc)
            return {
                "reply": "I have your request, but I could not save the lead right now. Let me connect you with our team.",
                "action": "escalated",
            }

    display_name = contact["name"] or "there"
    return {
        "reply": f"Thanks {display_name}, I captured your request and our team will contact you.",
        "action": "lead_captured",
    }


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

    # 3a. Lead capture shortcut -----------------------------------------
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
