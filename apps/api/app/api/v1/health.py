"""Health and readiness endpoints.

Hanan owns backend stability checks.
Ali Faddel consumes readiness signals in CI and deployment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from apps.api.app.core.config import AppSettings, get_settings
from apps.api.app.db.repository import InMemoryPlatformRepository
from apps.api.app.services.audit_service import AuditTrail


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class DependencyStatus:
    """Simple readiness marker for one subsystem."""

    name: str
    ready: bool
    detail: str = ""


@dataclass(slots=True)
class HealthReport:
    """Summarized health state for the platform spine."""

    service: str
    status: str
    ready: bool
    checked_at: datetime
    tenant_count: int
    document_count: int
    conversation_count: int
    lead_count: int
    audit_event_count: int
    dependencies: tuple[DependencyStatus, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "service": self.service,
            "status": self.status,
            "ready": self.ready,
            "checked_at": self.checked_at.isoformat(),
            "tenant_count": self.tenant_count,
            "document_count": self.document_count,
            "conversation_count": self.conversation_count,
            "lead_count": self.lead_count,
            "audit_event_count": self.audit_event_count,
            "dependencies": [
                {"name": dependency.name, "ready": dependency.ready, "detail": dependency.detail}
                for dependency in self.dependencies
            ],
            "metadata": self.metadata,
        }


def build_health_report(
    *,
    settings: AppSettings | None = None,
    repository: InMemoryPlatformRepository,
    audit_trail: AuditTrail | None = None,
) -> HealthReport:
    """Build a readiness report without needing a live database driver."""

    settings = settings or get_settings()
    tenant_count = len(repository.tenants)
    document_count = sum(len(documents) for documents in repository.documents.values())
    conversation_count = sum(len(conversations) for conversations in repository.conversations.values())
    lead_count = sum(len(leads) for leads in repository.leads.values())
    audit_event_count = len(audit_trail.events) if audit_trail is not None else 0
    dependencies = (
        DependencyStatus("postgres", bool(settings.database_url), settings.database_url),
        DependencyStatus("redis", bool(settings.redis_url), settings.redis_url),
        DependencyStatus("minio", bool(settings.minio_endpoint), settings.minio_endpoint),
        DependencyStatus("vault", bool(settings.vault_addr), settings.vault_addr),
    )
    ready = all(dependency.ready for dependency in dependencies)
    return HealthReport(
        service=settings.app_name,
        status="ok" if ready else "degraded",
        ready=ready,
        checked_at=_utcnow(),
        tenant_count=tenant_count,
        document_count=document_count,
        conversation_count=conversation_count,
        lead_count=lead_count,
        audit_event_count=audit_event_count,
        dependencies=dependencies,
        metadata={"environment": settings.app_env, "service_name": settings.otel_service_name},
    )
