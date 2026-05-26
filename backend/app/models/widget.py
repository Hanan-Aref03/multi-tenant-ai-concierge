"""Widget SQLAlchemy model — one embeddable chat widget per tenant."""
import uuid
from datetime import datetime
from typing import List

from sqlalchemy import ARRAY, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Widget(Base):
    __tablename__ = "widgets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    widget_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    greeting: Mapped[str] = mapped_column(Text, nullable=False, default="Hi! How can I help you?")
    accent_colour: Mapped[str] = mapped_column(String(7), nullable=False, default="#3B82F6")
    allowed_origins: Mapped[List[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now(), onupdate=func.now())
