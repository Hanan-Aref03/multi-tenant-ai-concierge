"""Lead table model placeholder.

Mohammad owns lead persistence and retention rules.
Ali Faddel surfaces lead visibility in the admin UI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LeadStatus(str, Enum):
    """Lifecycle states for captured leads."""

    NEW = "new"
    QUALIFIED = "qualified"
    ESCALATED = "escalated"
    CLOSED = "closed"


@dataclass(slots=True)
class Lead:
    """Tenant-scoped captured lead."""

    tenant_id: str
    lead_id: str
    full_name: str
    email: str
    company: str | None = None
    intent: str | None = None
    source: str = "widget"
    status: LeadStatus = LeadStatus.NEW
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)

    def touch(self) -> None:
        self.updated_at = _utcnow()

    def qualify(self) -> None:
        self.status = LeadStatus.QUALIFIED
        self.touch()

    def escalate(self, reason: str | None = None) -> None:
        self.status = LeadStatus.ESCALATED
        if reason:
            self.metadata["escalation_reason"] = reason
        self.touch()
