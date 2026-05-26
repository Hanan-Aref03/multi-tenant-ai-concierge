"""TenantConfig SQLAlchemy model — per-tenant agent persona + guardrail settings."""
import uuid
from datetime import datetime
from typing import List
from sqlalchemy import ARRAY, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

VALID_TOOLS = ["rag_search", "capture_lead", "escalate"]
VALID_TONES = ["polite", "firm", "brief"]


class TenantConfig(Base):
    __tablename__ = "tenant_config"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, unique=True, index=True)
    agent_persona: Mapped[str] = mapped_column(Text, nullable=False, default="You are a helpful assistant.")
    enabled_tools: Mapped[List[str]] = mapped_column(ARRAY(Text), nullable=False, default=lambda: list(VALID_TOOLS))
    allowed_topics: Mapped[List[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    blocked_topics: Mapped[List[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    refusal_tone: Mapped[str] = mapped_column(String(16), nullable=False, default="polite")
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now(), onupdate=func.now())
