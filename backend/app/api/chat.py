"""Chat API — receives visitor messages and runs the real assistant flow.

POST /api/chat — authenticated with widget session JWT
tenant_id is extracted exclusively from the verified token.
"""
import json
import logging
import os
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.widget_auth import WidgetTokenClaims, require_widget_token
from app.services.assistant_service import process_message
from apps.shared.llm_client import build_llm_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])

_MEMORY_KEY_FMT = "conv:{tenant_id}:{session_id}"
_MEMORY_TTL = 1_800  # 30 minutes

_redis: Any = None
_llm: Any = None


def _get_redis():
    """Return a cached async Redis client, or None if Redis is unavailable."""
    global _redis
    if _redis is None:
        try:
            import redis.asyncio as aioredis  # type: ignore[import]

            _redis = aioredis.from_url(
                os.getenv("REDIS_URL", "redis://localhost:6379/0"),
                decode_responses=True,
            )
        except Exception as exc:  # pragma: no cover - runtime fallback
            logger.warning("Redis client unavailable: %s", exc)
    return _redis


def _get_llm():
    """Return the shared Gemini/OpenAI-compatible client, or None."""
    global _llm
    if _llm is None:
        _llm = build_llm_client()
        if _llm is None:
            logger.warning("No Gemini/OpenAI LLM client configured; LLM disabled")
    return _llm


def _get_classifier_url() -> str | None:
    return os.getenv("CLASSIFIER_URL") or None


async def _load_history(redis, tenant_id: str, session_id: str) -> List[Dict[str, Any]]:
    """Load message history from Redis, returning [] on cache miss or error."""
    if redis is None:
        return []
    key = _MEMORY_KEY_FMT.format(tenant_id=tenant_id, session_id=session_id)
    try:
        raw = await redis.get(key)
        if raw:
            return json.loads(raw)
    except Exception as exc:
        logger.warning(
            "Failed to load conversation history (tenant=%s session=%s): %s",
            tenant_id,
            session_id,
            exc,
        )
    return []


async def _save_history(redis, tenant_id: str, session_id: str, messages: List[Dict[str, Any]]) -> None:
    """Persist updated message list to Redis with a rolling TTL."""
    if redis is None:
        return
    key = _MEMORY_KEY_FMT.format(tenant_id=tenant_id, session_id=session_id)
    try:
        await redis.set(key, json.dumps(messages), ex=_MEMORY_TTL)
    except Exception as exc:
        logger.warning(
            "Failed to save conversation history (tenant=%s session=%s): %s",
            tenant_id,
            session_id,
            exc,
        )


class ChatRequest(BaseModel):
    conversation_id: str
    message: str
    # NOTE: any tenant_id field in the body is intentionally absent from this schema.
    # It is derived from the verified JWT only. Adding it here would be a security hole.


class ChatResponse(BaseModel):
    reply: str
    conversation_id: str


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    claims: WidgetTokenClaims = Depends(require_widget_token),
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    """Process a visitor chat message.

    tenant_id comes from the verified JWT claims — never from the request body.
    The assistant flow uses the router-first / agent-second path.
    """
    if body.conversation_id != str(claims.conversation_id):
        raise HTTPException(status_code=403, detail="Conversation ID mismatch")

    tenant_id = str(claims.tenant_id)
    session_id = body.conversation_id

    redis = _get_redis()
    llm_client = _get_llm()
    conversation_history: List[Dict[str, Any]] = await _load_history(redis, tenant_id, session_id)

    try:
        result = await process_message(
            tenant_id=tenant_id,
            session_id=session_id,
            message=body.message,
            conversation_history=conversation_history,
            db_session=db,
            redis_client=redis,
            llm_client=llm_client,
            classifier_url=_get_classifier_url(),
        )
    except Exception as exc:
        logger.error("process_message failed for tenant=%s session=%s: %s", tenant_id, session_id, exc)
        raise HTTPException(status_code=500, detail="Failed to process chat message.")

    updated_history = conversation_history + [
        {"role": "user", "content": body.message},
        {"role": "assistant", "content": result.get("reply", "")},
    ]
    await _save_history(redis, tenant_id, session_id, updated_history)

    return ChatResponse(reply=result.get("reply", ""), conversation_id=body.conversation_id)
