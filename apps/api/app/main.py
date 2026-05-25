"""Hanan owns the FastAPI backbone.

Hanan owns auth, tenant context, and request-scoped security.
Mohammad owns the agent, RAG, and memory services behind the API.
Ali Faddel owns the public API contract consumed by widget and admin.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from typing import Any

try:  # pragma: no cover - optional dependency for later app wiring
    from fastapi import FastAPI  # type: ignore
except Exception:  # pragma: no cover - FastAPI is optional in this scaffold
    FastAPI = None  # type: ignore[assignment]

from apps.api.app.api.router import RouteCatalog, build_route_catalog
from apps.api.app.api.v1.health import HealthReport, build_health_report
from apps.api.app.api.v1.tenants import TenantPlatformService
from apps.api.app.core.config import AppSettings, get_settings
from apps.api.app.core.tenant_context import TenantRequestContext
from apps.api.app.db.repository import InMemoryPlatformRepository
from apps.api.app.db.session import RlsSessionSettings, build_rls_session_settings
from apps.api.app.services.audit_service import AuditTrail


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class PlatformApplication:
    """Composition root for the platform spine."""

    settings: AppSettings
    repository: InMemoryPlatformRepository
    audit_trail: AuditTrail
    route_catalog: RouteCatalog
    tenant_service: TenantPlatformService
    created_at: datetime = field(default_factory=_utcnow)

    def refresh_health_report(self) -> HealthReport:
        return build_health_report(
            settings=self.settings,
            repository=self.repository,
            audit_trail=self.audit_trail,
        )

    def build_session_settings(self, context: TenantRequestContext) -> RlsSessionSettings:
        return build_rls_session_settings(context)

    def summary(self) -> dict[str, Any]:
        report = self.refresh_health_report()
        return {
            "app_name": self.settings.app_name,
            "environment": self.settings.app_env,
            "routes": len(self.route_catalog.routes),
            "implemented_routes": len(self.route_catalog.implemented_routes()),
            "tenants": report.tenant_count,
            "documents": report.document_count,
            "conversations": report.conversation_count,
            "leads": report.lead_count,
            "audit_events": report.audit_event_count,
            "ready": report.ready,
        }


def build_platform_application(
    *,
    settings: AppSettings | None = None,
    repository: InMemoryPlatformRepository | None = None,
    audit_trail: AuditTrail | None = None,
) -> PlatformApplication:
    """Create the dependency graph for the platform spine."""

    settings = settings or get_settings()
    repository = repository or InMemoryPlatformRepository()
    audit_trail = audit_trail or AuditTrail()
    route_catalog = build_route_catalog()
    tenant_service = TenantPlatformService(
        repository=repository,
        audit_trail=audit_trail,
        settings=settings,
    )
    return PlatformApplication(
        settings=settings,
        repository=repository,
        audit_trail=audit_trail,
        route_catalog=route_catalog,
        tenant_service=tenant_service,
    )


def build_fastapi_app() -> Any:
    """Build a real FastAPI app when the dependency is installed."""

    if FastAPI is None:
        raise RuntimeError("FastAPI is not installed in this environment")
    platform = build_platform_application()
    app = FastAPI(title=platform.settings.app_name, version="0.1.0")
    app.state.platform = platform
    return app


def main() -> None:
    """CLI-friendly entry point used by the local compose stack."""

    platform = build_platform_application()
    print(json.dumps(platform.summary(), sort_keys=True))


if __name__ == "__main__":
    main()
