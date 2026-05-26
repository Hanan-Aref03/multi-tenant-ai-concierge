"""Widget API — token exchange and public config endpoints.

POST /api/widget/token   — exchange widget_id for a signed session JWT
GET  /api/widget/{widget_id}/config — public theme config (no auth)
"""
import re
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.widget import Widget
from app.models.widget_session import WidgetSession
from app.services.origin_check import get_allowed_origins, verify_origin
from app.services.widget_token import issue_widget_token

settings = get_settings()
router = APIRouter(prefix="/api/widget", tags=["widget"])

_COLOUR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


class TokenRequest(BaseModel):
    widget_id: str


class TokenResponse(BaseModel):
    token: str
    conversation_id: str
    expires_in: int


class WidgetConfig(BaseModel):
    greeting: str
    accent_colour: str


@router.post("/token", response_model=TokenResponse)
async def exchange_token(
    body: TokenRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Exchange a public widget_id for a short-lived signed session token.

    Server-side origin check is the real auth boundary — CORS is defense-in-depth.
    tenant_id is always derived from the DB, never from the request body.
    """
    # 1. Validate origin (raises 403 if not allowed)
    await verify_origin(request, body.widget_id, db)

    # 2. Look up widget
    result = await db.execute(select(Widget).where(Widget.widget_id == body.widget_id))
    widget = result.scalar_one_or_none()
    if widget is None:
        raise HTTPException(status_code=404, detail="Widget not found")

    # 3. Issue token
    conversation_id = uuid.uuid4()
    origin = request.headers.get("origin") or request.headers.get("Origin") or ""
    token = issue_widget_token(
        tenant_id=widget.tenant_id,
        widget_id=widget.widget_id,
        conversation_id=conversation_id,
        origin=origin,
    )

    # 4. Audit record
    now = datetime.now(UTC).replace(tzinfo=None)
    session = WidgetSession(
        tenant_id=widget.tenant_id,
        widget_id=widget.id,
        conversation_id=conversation_id,
        origin=origin,
        issued_at=now,
        expires_at=now + timedelta(seconds=settings.widget_token_expire_seconds),
    )
    db.add(session)
    await db.commit()

    return TokenResponse(
        token=token,
        conversation_id=str(conversation_id),
        expires_in=settings.widget_token_expire_seconds,
    )


@router.get("/{widget_id}/config", response_model=WidgetConfig)
async def get_widget_config(widget_id: str, db: AsyncSession = Depends(get_db)) -> WidgetConfig:
    """Public endpoint — returns theme config. No auth required. Cache-friendly."""
    result = await db.execute(select(Widget).where(Widget.widget_id == widget_id))
    widget = result.scalar_one_or_none()
    if widget is None:
        raise HTTPException(status_code=404, detail="Widget not found")
    return WidgetConfig(greeting=widget.greeting, accent_colour=widget.accent_colour)
