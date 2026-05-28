"""Admin API — tenant_admin-only endpoints for widget + agent config + leads.

All reads and writes are scoped to the authenticated tenant via RLS.
A tenant_admin cannot access another tenant's data by construction.
"""
import os
import re
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.tenant_config import VALID_TOOLS, VALID_TONES, TenantConfig
from app.models.widget import Widget
from app.services.origin_check import invalidate_origins_cache

router = APIRouter(prefix="/api/admin", tags=["admin"])

_COLOUR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
_ORIGIN_RE = re.compile(r"^https?://[a-z0-9.-]+(:\d+)?$")


# ── Placeholder auth dependency (Owner A provides full JWT role middleware) ──
async def require_tenant_admin() -> uuid.UUID:
    """Stub: returns a fixed tenant_id. Owner A replaces with real JWT role check."""
    return uuid.UUID("00000000-0000-0000-0000-000000000001")


async def _get_or_create_widget(
    tenant_id: uuid.UUID,
    db: AsyncSession,
) -> Widget:
    """Return the tenant widget, seeding a safe default for the demo stack."""
    result = await db.execute(select(Widget).where(Widget.tenant_id == tenant_id))
    widget = result.scalar_one_or_none()
    if widget is not None:
        return widget

    widget = Widget(
        tenant_id=tenant_id,
        widget_id=f"tenant-{tenant_id.hex[:8]}-widget",
        greeting="Hi! How can I help you?",
        accent_colour="#3B82F6",
        allowed_origins=_default_allowed_origins(),
    )
    db.add(widget)
    await db.commit()
    await db.refresh(widget)
    return widget


def _default_allowed_origins() -> list[str]:
    raw = os.getenv("WIDGET_ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


async def _get_or_create_config(
    tenant_id: uuid.UUID,
    db: AsyncSession,
) -> TenantConfig:
    """Return the tenant config, seeding a safe default for the demo stack."""
    result = await db.execute(select(TenantConfig).where(TenantConfig.tenant_id == tenant_id))
    cfg = result.scalar_one_or_none()
    if cfg is not None:
        return cfg

    cfg = TenantConfig(tenant_id=tenant_id)
    cfg.agent_persona = "You are a helpful assistant."
    cfg.enabled_tools = list(VALID_TOOLS)
    cfg.allowed_topics = []
    cfg.blocked_topics = []
    cfg.refusal_tone = "polite"
    db.add(cfg)
    await db.commit()
    await db.refresh(cfg)
    return cfg


# ─────────────────────────────────────────────────────────────────────────────
# Widget config
# ─────────────────────────────────────────────────────────────────────────────

class WidgetUpdateRequest(BaseModel):
    greeting: Optional[str] = None
    accent_colour: Optional[str] = None
    allowed_origins: Optional[List[str]] = None

    @field_validator("accent_colour")
    @classmethod
    def validate_colour(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not _COLOUR_RE.match(v):
            raise ValueError("accent_colour must be a 6-digit hex colour e.g. #3B82F6")
        return v

    @field_validator("allowed_origins")
    @classmethod
    def validate_origins(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is not None:
            for o in v:
                if not _ORIGIN_RE.match(o):
                    raise ValueError(f"Invalid origin: {o!r} — must be https://host or http://host:port")
        return v


class WidgetResponse(BaseModel):
    widget_id: str
    greeting: str
    accent_colour: str
    allowed_origins: List[str]
    embed_snippet: str


@router.get("/widget", response_model=WidgetResponse)
async def get_widget_config(
    tenant_id: uuid.UUID = Depends(require_tenant_admin),
    db: AsyncSession = Depends(get_db),
) -> WidgetResponse:
    widget = await _get_or_create_widget(tenant_id, db)
    return _widget_response(widget)


@router.put("/widget", response_model=WidgetResponse)
async def update_widget_config(
    body: WidgetUpdateRequest,
    tenant_id: uuid.UUID = Depends(require_tenant_admin),
    db: AsyncSession = Depends(get_db),
) -> WidgetResponse:
    widget = await _get_or_create_widget(tenant_id, db)

    if body.greeting is not None:
        widget.greeting = body.greeting
    if body.accent_colour is not None:
        widget.accent_colour = body.accent_colour
    if body.allowed_origins is not None:
        widget.allowed_origins = body.allowed_origins
        await invalidate_origins_cache(widget.widget_id)

    await db.commit()
    await db.refresh(widget)
    return _widget_response(widget)


def _widget_response(widget: Widget) -> WidgetResponse:
    api_base_url = os.getenv("PUBLIC_API_BASE_URL", "http://localhost:8000").rstrip("/")
    snippet = (
        f'<script src="{api_base_url}/widget.js" '
        f'data-widget-id="{widget.widget_id}" '
        f'data-api-base="{api_base_url}"></script>'
    )
    return WidgetResponse(
        widget_id=widget.widget_id,
        greeting=widget.greeting,
        accent_colour=widget.accent_colour,
        allowed_origins=widget.allowed_origins,
        embed_snippet=snippet,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Agent + guardrail config
# ─────────────────────────────────────────────────────────────────────────────

class ConfigUpdateRequest(BaseModel):
    agent_persona: Optional[str] = None
    enabled_tools: Optional[List[str]] = None
    allowed_topics: Optional[List[str]] = None
    blocked_topics: Optional[List[str]] = None
    refusal_tone: Optional[str] = None

    @field_validator("enabled_tools")
    @classmethod
    def validate_tools(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is not None:
            invalid = set(v) - set(VALID_TOOLS)
            if invalid:
                raise ValueError(f"Invalid tools: {invalid}. Must be subset of {VALID_TOOLS}")
        return v

    @field_validator("refusal_tone")
    @classmethod
    def validate_tone(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_TONES:
            raise ValueError(f"refusal_tone must be one of {VALID_TONES}")
        return v


class ConfigResponse(BaseModel):
    agent_persona: str
    enabled_tools: List[str]
    allowed_topics: List[str]
    blocked_topics: List[str]
    refusal_tone: str


@router.get("/config", response_model=ConfigResponse)
async def get_agent_config(
    tenant_id: uuid.UUID = Depends(require_tenant_admin),
    db: AsyncSession = Depends(get_db),
) -> ConfigResponse:
    cfg = await _get_or_create_config(tenant_id, db)
    return ConfigResponse(
        agent_persona=cfg.agent_persona,
        enabled_tools=cfg.enabled_tools,
        allowed_topics=cfg.allowed_topics,
        blocked_topics=cfg.blocked_topics,
        refusal_tone=cfg.refusal_tone,
    )


@router.put("/config", response_model=ConfigResponse)
async def update_agent_config(
    body: ConfigUpdateRequest,
    tenant_id: uuid.UUID = Depends(require_tenant_admin),
    db: AsyncSession = Depends(get_db),
) -> ConfigResponse:
    cfg = await _get_or_create_config(tenant_id, db)

    for field in ("agent_persona", "enabled_tools", "allowed_topics", "blocked_topics", "refusal_tone"):
        value = getattr(body, field)
        if value is not None:
            setattr(cfg, field, value)

    await db.commit()
    await db.refresh(cfg)
    return ConfigResponse(
        agent_persona=cfg.agent_persona,
        enabled_tools=cfg.enabled_tools,
        allowed_topics=cfg.allowed_topics,
        blocked_topics=cfg.blocked_topics,
        refusal_tone=cfg.refusal_tone,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Leads (read-only)
# ─────────────────────────────────────────────────────────────────────────────

class LeadItem(BaseModel):
    id: str
    visitor_name: Optional[str]
    contact: str
    intent: str
    captured_at: str


class LeadsResponse(BaseModel):
    total: int
    leads: List[LeadItem]


@router.get("/leads", response_model=LeadsResponse)
async def get_leads(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    tenant_id: uuid.UUID = Depends(require_tenant_admin),
    db: AsyncSession = Depends(get_db),
) -> LeadsResponse:
    """Read-only leads for this tenant. RLS ensures cross-tenant isolation."""
    # Owner B owns the Lead model; we import it lazily to avoid circular imports
    try:
        from app.models.lead import Lead  # type: ignore[import]
        from sqlalchemy import func as sqlfunc

        count_result = await db.execute(
            select(sqlfunc.count()).select_from(Lead).where(Lead.tenant_id == tenant_id)
        )
        total = count_result.scalar_one()

        rows_result = await db.execute(
            select(Lead)
            .where(Lead.tenant_id == tenant_id)
            .order_by(Lead.captured_at.desc())
            .limit(limit)
            .offset(offset)
        )
        leads = rows_result.scalars().all()
        return LeadsResponse(
            total=total,
            leads=[
                LeadItem(
                    id=str(lead.id),
                    visitor_name=lead.visitor_name,
                    contact=lead.contact,
                    intent=lead.intent,
                    captured_at=lead.captured_at.isoformat(),
                )
                for lead in leads
            ],
        )
    except ImportError:
        # Lead model not yet defined by Owner B — return empty stub
        return LeadsResponse(total=0, leads=[])
