"""Audit logging and security event recording.

Hanan owns the sensitive action log path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuditOutcome(str, Enum):
    """Result status for an audit event."""

    SUCCESS = "success"
    DENIED = "denied"
    FAILED = "failed"


@dataclass(slots=True)
class AuditEvent:
    """One immutable audit event."""

    event_id: str
    tenant_id: str | None
    actor: str
    action: str
    resource_type: str
    resource_id: str
    outcome: AuditOutcome = AuditOutcome.SUCCESS
    details: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utcnow)


@dataclass(slots=True)
class AuditTrail:
    """In-memory audit trail used by the platform spine."""

    events: list[AuditEvent] = field(default_factory=list)

    def record(self, event: AuditEvent) -> AuditEvent:
        self.events.append(event)
        return event

    def record_action(
        self,
        *,
        tenant_id: str | None,
        actor: str,
        action: str,
        resource_type: str,
        resource_id: str,
        outcome: AuditOutcome = AuditOutcome.SUCCESS,
        details: dict[str, Any] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            event_id=f"audit_{uuid4().hex[:12]}",
            tenant_id=tenant_id,
            actor=actor,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            outcome=outcome,
            details=details or {},
        )
        return self.record(event)

    def tenant_events(self, tenant_id: str) -> list[AuditEvent]:
        return [event for event in self.events if event.tenant_id == tenant_id]

    def summary(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for event in self.events:
            counts[event.action] = counts.get(event.action, 0) + 1
        return counts
