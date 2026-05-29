"""Conversation and lead endpoints.

Mohammad owns the assistant flow.
Hanan owns persistence and audit logging.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from apps.shared.llm_client import build_llm_client
from apps.api.app.services.agent_service import process_message

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Redis constants — must match services/agent/agent.py
# ---------------------------------------------------------------------------

_MEMORY_KEY_FMT = "conv:{tenant_id}:{session_id}"
_MEMORY_TTL = 1_800  # 30 minutes

# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class MessageRequest(BaseModel):
    session_id: str = Field(..., description="Stable identifier for this conversation session")
    message: str = Field(..., min_length=1, max_length=4_096, description="User message text")


class MessageResponse(BaseModel):
    reply: str
    intent: str
    action: Optional[str] = None
    sources: List[Dict[str, Any]] = []
    rag_confidence: float = 0.0


class ConversationTurn(BaseModel):
    role: str
    content: str


class ConversationHistoryResponse(BaseModel):
    session_id: str
    tenant_id: str
    messages: List[ConversationTurn]


# ---------------------------------------------------------------------------
# Dependencies — follow the same safe-import pattern as content.py
# ---------------------------------------------------------------------------

try:
    from apps.api.app.core.tenant_context import get_current_tenant_id
except ImportError:
    logger.warning("get_current_tenant_id not available; using dev fallback")

    def get_current_tenant_id() -> str:  # type: ignore[misc]
        return "dev-tenant-123"


try:
    from apps.api.app.db.session import get_db
except ImportError:
    logger.warning("get_db not available; using no-op fallback")

    async def get_db():  # type: ignore[misc]
        yield None


# ---------------------------------------------------------------------------
# Redis & LLM client singletons — lazy, env-configured
# ---------------------------------------------------------------------------

_redis: Any = None
_llm: Any = None


def _get_redis():
    """Return a cached async Redis client, or None if unavailable."""
    global _redis
    if _redis is None:
        try:
            import redis.asyncio as aioredis  # type: ignore[import]

            _redis = aioredis.from_url(
                os.getenv("REDIS_URL", "redis://localhost:6379/0"),
                decode_responses=True,
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("Redis client unavailable: %s", exc)
    return _redis


def _get_llm():
    """Return a cached async LLM client, or None if unconfigured."""
    global _llm
    if _llm is None:
        _llm = build_llm_client()
        if _llm is None:
            logger.warning("No Gemini/OpenAI LLM client configured; LLM disabled")
    return _llm


def _get_classifier_url() -> Optional[str]:
    """Return Rayan's model server URL from env, or None to fall back to LLM."""
    return os.getenv("CLASSIFIER_URL") or None


# ---------------------------------------------------------------------------
# Conversation history helpers
# ---------------------------------------------------------------------------


async def _load_history(redis, tenant_id: str, session_id: str) -> List[Dict]:
    """Load message list from Redis. Returns [] on cache miss or error."""
    if redis is None:
        return []
    key = _MEMORY_KEY_FMT.format(tenant_id=tenant_id, session_id=session_id)
    try:
        raw = await redis.get(key)
        if raw:
            return json.loads(raw)
    except Exception as exc:
        logger.warning("Failed to load conversation history (tenant=%s session=%s): %s",
                       tenant_id, session_id, exc)
    return []


async def _save_history(redis, tenant_id: str, session_id: str, messages: List[Dict]) -> None:
    """Persist updated message list to Redis with a rolling TTL."""
    if redis is None:
        return
    key = _MEMORY_KEY_FMT.format(tenant_id=tenant_id, session_id=session_id)
    try:
        await redis.set(key, json.dumps(messages), ex=_MEMORY_TTL)
    except Exception as exc:
        logger.warning("Failed to save conversation history (tenant=%s session=%s): %s",
                       tenant_id, session_id, exc)


# ---------------------------------------------------------------------------
# POST /message  (4E.1)
# ---------------------------------------------------------------------------


@router.post("/message", response_model=MessageResponse, status_code=status.HTTP_200_OK)
async def send_message(
    payload: MessageRequest,
    tenant_id: str = Depends(get_current_tenant_id),
    db=Depends(get_db),
):
    """
    Send a user message and receive a routed reply.

    Flow:
    1. Load conversation history from Redis.
    2. Classify intent via services.router.classifier_service.classify_intent().
    3. Route: direct (greeting/off_topic) | RAG (faq/knowledge_search) | agent.
    4. Append user + assistant turns and save history back to Redis.
    5. Return reply, intent, action, and optional RAG sources.
    """
    redis = _get_redis()
    llm = _get_llm()
    classifier_url = _get_classifier_url()

    # 1. Load history ----------------------------------------------------
    history = await _load_history(redis, tenant_id, payload.session_id)

    # 2+3. Route and respond ---------------------------------------------
    try:
        result = await process_message(
            tenant_id=tenant_id,
            session_id=payload.session_id,
            message=payload.message,
            conversation_history=history,
            db_session=db,
            redis_client=redis,
            llm_client=llm,
            classifier_url=classifier_url,
        )
    except Exception as exc:
        logger.error(
            "process_message failed: tenant=%s session=%s: %s",
            tenant_id, payload.session_id, exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process message.",
        )

    # 4. Persist history (for direct + RAG paths; agent path saves internally)
    updated_history = history + [
        {"role": "user", "content": payload.message},
        {"role": "assistant", "content": result.get("reply", "")},
    ]
    await _save_history(redis, tenant_id, payload.session_id, updated_history)

    return MessageResponse(
        reply=result.get("reply", ""),
        intent=result.get("intent", "unknown"),
        action=result.get("action"),
        sources=result.get("sources", []),
        rag_confidence=result.get("rag_confidence", 0.0),
    )


# ---------------------------------------------------------------------------
# GET /{session_id}  (4E.2)
# ---------------------------------------------------------------------------


@router.get("/{session_id}", response_model=ConversationHistoryResponse)
async def get_conversation(
    session_id: str,
    tenant_id: str = Depends(get_current_tenant_id),
):
    """
    Return the conversation history for a session, scoped to the current tenant.

    Only user and assistant turns are returned; system and tool messages are
    stripped so the response is safe to surface to client applications.
    """
    redis = _get_redis()
    history = await _load_history(redis, tenant_id, session_id)

    visible_turns = [
        ConversationTurn(role=m["role"], content=m.get("content", ""))
        for m in history
        if m.get("role") in ("user", "assistant")
    ]

    return ConversationHistoryResponse(
        session_id=session_id,
        tenant_id=tenant_id,
        messages=visible_turns,
    )
