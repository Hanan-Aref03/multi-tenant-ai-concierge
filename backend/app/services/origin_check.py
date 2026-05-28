"""Origin validation service — DB lookup + Redis cache + server-side 403.

CORS headers are defense-in-depth. This check is the real boundary.
"""
import json
from typing import Optional

import redis.asyncio as aioredis
from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.widget import Widget

settings = get_settings()

_redis: Optional[aioredis.Redis] = None


def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def get_allowed_origins(widget_id: str, db: AsyncSession) -> list[str]:
    """Fetch allowed_origins for a widget_id, with Redis cache (TTL 60 s)."""
    cache_key = f"widget_origins:{widget_id}"
    redis = _get_redis()
    if redis is not None:
        try:
            cached = await redis.get(cache_key)
            if cached is not None:
                return json.loads(cached)
        except Exception:
            # Redis is a cache, not a dependency. Fall through to the DB.
            pass

    result = await db.execute(select(Widget).where(Widget.widget_id == widget_id))
    widget = result.scalar_one_or_none()
    if widget is None:
        return []

    origins = widget.allowed_origins or []
    if redis is not None:
        try:
            await redis.setex(cache_key, settings.cors_cache_ttl_seconds, json.dumps(origins))
        except Exception:
            pass
    return origins


async def invalidate_origins_cache(widget_id: str) -> None:
    """Call after admin updates allowed_origins so the cache refreshes."""
    redis = _get_redis()
    if redis is None:
        return
    try:
        await redis.delete(f"widget_origins:{widget_id}")
    except Exception:
        pass


async def verify_origin(request: Request, widget_id: str, db: AsyncSession) -> None:
    """Raise HTTP 403 if the request Origin is not in the widget's allowed_origins.

    Use as a FastAPI dependency on the token exchange endpoint.
    An absent Origin header is treated as disallowed (non-browser caller).
    An empty allowed_origins list blocks all origins.
    """
    origin = request.headers.get("origin") or request.headers.get("Origin")
    if not origin:
        raise HTTPException(status_code=403, detail="Origin header required")

    allowed = await get_allowed_origins(widget_id, db)
    if not allowed or origin not in allowed:
        raise HTTPException(status_code=403, detail="Origin not permitted")
