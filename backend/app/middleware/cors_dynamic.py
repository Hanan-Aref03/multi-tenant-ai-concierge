"""Dynamic CORS + CSP middleware — reads allowed_origins from DB per request.

CORS and CSP frame-ancestors are defense-in-depth around the signed token.
They are NOT the auth boundary.
"""
import json
from typing import Optional

import redis.asyncio as aioredis
from fastapi import Request
from fastapi.responses import Response
from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.config import get_settings
from app.models.widget import Widget

settings = get_settings()


class DynamicCORSMiddleware(BaseHTTPMiddleware):
    """Sets Access-Control-Allow-Origin and Content-Security-Policy: frame-ancestors
    based on the tenant's allowed_origins stored in the database.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._redis: Optional[aioredis.Redis] = None

    def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        return self._redis

    async def _get_origins_for_widget(self, widget_id: str, request: Request) -> list[str]:
        redis = self._get_redis()
        cache_key = f"widget_origins:{widget_id}"
        cached = await redis.get(cache_key)
        if cached is not None:
            return json.loads(cached)

        # Lazy DB lookup — only when cache cold
        db = request.state.db if hasattr(request.state, "db") else None
        if db is None:
            return []
        result = await db.execute(select(Widget).where(Widget.widget_id == widget_id))
        widget = result.scalar_one_or_none()
        origins = widget.allowed_origins if widget else []
        await redis.setex(cache_key, settings.cors_cache_ttl_seconds, json.dumps(origins))
        return origins

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        response: Response = await call_next(request)

        origin = request.headers.get("origin") or request.headers.get("Origin")
        widget_id = request.query_params.get("widget_id") or request.path_params.get("widget_id")

        if origin and widget_id:
            allowed = await self._get_origins_for_widget(widget_id, request)
            if origin in allowed:
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Access-Control-Allow-Credentials"] = "true"
                response.headers["Vary"] = "Origin"
                # CSP frame-ancestors: only allowed origins may embed the widget
                csp_origins = " ".join(allowed)
                response.headers["Content-Security-Policy"] = (
                    f"frame-ancestors 'self' {csp_origins}"
                )

        return response
