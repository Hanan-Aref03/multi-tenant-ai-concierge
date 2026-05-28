"""Chat API - receives visitor messages and runs the concierge pipeline.

POST /api/chat is authenticated with a widget session JWT. Runtime context
comes exclusively from verified token claims, never from client body fields.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

import httpx
import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.middleware.widget_auth import WidgetTokenClaims, require_widget_token
from apps.api.app.services.agent_service import process_message
from apps.shared.llm_client import build_llm_client
from apps.shared.service_auth import get_service_token

router = APIRouter(prefix="/api", tags=["chat"])
logger = logging.getLogger(__name__)
settings = get_settings()

_MEMORY_KEY_FMT = "conv:{tenant_id}:{session_id}"
_MEMORY_TTL = 1_800
_redis: Any = None
_llm: Any = None

_SAFE_REFUSAL = (
    "I can't help with that request. I can still help with product, "
    "service, or support questions."
)
_LEAD_KEYWORDS = (
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
_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE_RE = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")


def _get_redis():
    """Return a cached async Redis client for short-term widget memory."""
    global _redis
    if _redis is None:
        try:
            _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        except Exception as exc:  # pragma: no cover - runtime fallback
            logger.warning("Redis client unavailable: %s", exc)
    return _redis


def _get_llm():
    """Return a cached OpenAI-compatible LLM client, or None if unconfigured."""
    global _llm
    if _llm is None:
        _llm = build_llm_client()
        if _llm is None:
            logger.warning("No Gemini/OpenAI LLM client configured; LLM disabled")
    return _llm


def _classifier_url() -> Optional[str]:
    return settings.classifier_url or None


def _should_preserve_contact_text(message: str) -> bool:
    lowered = message.lower()
    has_sales_signal = any(keyword in lowered for keyword in _LEAD_KEYWORDS)
    has_contact = bool(_EMAIL_RE.search(message) or _PHONE_RE.search(message))
    return has_sales_signal and has_contact


async def _load_history(
    redis_client,
    tenant_id: str,
    conversation_id: str,
) -> List[Dict[str, Any]]:
    if redis_client is None:
        return []
    key = _MEMORY_KEY_FMT.format(tenant_id=tenant_id, session_id=conversation_id)
    try:
        raw = await redis_client.get(key)
        if raw:
            return json.loads(raw)
    except Exception as exc:
        logger.warning(
            "Failed to load widget chat history: tenant=%s session=%s error=%s",
            tenant_id,
            conversation_id,
            exc,
        )
    return []


async def _save_history(
    redis_client,
    tenant_id: str,
    conversation_id: str,
    history: List[Dict[str, Any]],
) -> None:
    if redis_client is None:
        return
    key = _MEMORY_KEY_FMT.format(tenant_id=tenant_id, session_id=conversation_id)
    try:
        await redis_client.set(key, json.dumps(history), ex=_MEMORY_TTL)
    except Exception as exc:
        logger.warning(
            "Failed to save widget chat history: tenant=%s session=%s error=%s",
            tenant_id,
            conversation_id,
            exc,
        )


async def _set_tenant_context(db: AsyncSession, tenant_id: str) -> None:
    """Set Postgres RLS context for tenant-scoped RAG/tool queries."""
    await db.execute(
        sa_text(
            "SELECT set_config('app.tenant_id', :tenant_id, true), "
            "set_config('app.actor_role', '', true)"
        ),
        {"tenant_id": tenant_id},
    )


async def _guardrails_check(tenant_id: str, message: str) -> Dict[str, Any]:
    """Call the guardrails sidecar before model routing or logging."""
    if not settings.guardrails_url:
        return {
            "allowed": True,
            "redacted_message": message,
            "decision": "allow",
            "reason": "disabled",
        }

    service_token = get_service_token()
    async with httpx.AsyncClient(timeout=3.0) as client:
        response = await client.post(
            f"{settings.guardrails_url.rstrip('/')}/v1/check",
            headers={"Authorization": f"Bearer {service_token}"},
            json={"tenant_id": tenant_id, "message": message},
        )
        response.raise_for_status()
        return response.json()


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    conversation_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1, max_length=4096)


class ChatResponse(BaseModel):
    reply: str
    conversation_id: str
    intent: str = "unknown"
    action: Optional[str] = None
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    rag_confidence: float = 0.0


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    claims: WidgetTokenClaims = Depends(require_widget_token),
) -> ChatResponse:
    """Process a visitor message through guardrails, classifier, router, RAG, and agent."""
    tenant_id = str(claims.tenant_id)
    conversation_id = str(claims.conversation_id)

    if body.conversation_id != conversation_id:
        raise HTTPException(status_code=403, detail="Conversation ID mismatch")

    request_origin = request.headers.get("origin") or request.headers.get("Origin") or ""
    if request_origin and request_origin != claims.origin:
        raise HTTPException(status_code=403, detail="Origin mismatch")

    try:
        guardrail = await _guardrails_check(tenant_id, body.message)
    except httpx.HTTPError as exc:
        logger.error(
            "Guardrails check failed: tenant=%s session=%s error=%s",
            tenant_id,
            conversation_id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Safety service unavailable.",
        ) from exc

    safe_message = str(guardrail.get("redacted_message") or body.message)
    if not guardrail.get("allowed", False):
        return ChatResponse(
            reply=_SAFE_REFUSAL,
            conversation_id=conversation_id,
            intent="blocked",
            action="blocked",
        )

    pipeline_message = body.message if _should_preserve_contact_text(body.message) else safe_message

    redis_client = _get_redis()
    history = await _load_history(redis_client, tenant_id, conversation_id)

    try:
        await _set_tenant_context(db, tenant_id)
        result = await process_message(
            tenant_id=tenant_id,
            session_id=conversation_id,
            message=pipeline_message,
            conversation_history=history,
            db_session=db,
            redis_client=redis_client,
            llm_client=_get_llm(),
            classifier_url=_classifier_url(),
        )
    except Exception as exc:
        logger.error(
            "Chat pipeline failed: tenant=%s session=%s widget=%s error=%s",
            tenant_id,
            conversation_id,
            claims.widget_id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process message.",
        ) from exc

    updated_history = history + [
        {"role": "user", "content": safe_message},
        {"role": "assistant", "content": result.get("reply", "")},
    ]
    await _save_history(redis_client, tenant_id, conversation_id, updated_history)

    return ChatResponse(
        reply=result.get("reply", ""),
        conversation_id=conversation_id,
        intent=result.get("intent", "unknown"),
        action=result.get("action"),
        sources=result.get("sources", []),
        rag_confidence=result.get("rag_confidence", 0.0),
    )
