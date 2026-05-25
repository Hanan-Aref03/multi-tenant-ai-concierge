"""Database session helpers.

Hanan owns the Postgres session lifecycle and RLS session variable setup.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator

from apps.api.app.core.tenant_context import TenantRequestContext


def _quote_sql(value: str) -> str:
    return value.replace("'", "''")


@dataclass(slots=True)
class RlsSessionSettings:
    """Session variables that Postgres RLS policies can consume."""

    tenant_id: str
    actor_role: str
    actor_subject: str
    request_id: str
    origin: str | None = None

    def as_postgres_settings(self) -> dict[str, str]:
        return {
            "app.tenant_id": self.tenant_id,
            "app.actor_role": self.actor_role,
            "app.actor_subject": self.actor_subject,
            "app.request_id": self.request_id,
        }

    def as_sql_prologue(self) -> tuple[str, ...]:
        statements = []
        for key, value in self.as_postgres_settings().items():
            statements.append(f"SELECT set_config('{key}', '{_quote_sql(value)}', true);")
        return tuple(statements)


@dataclass(slots=True)
class ScopedSession:
    """Lightweight session wrapper for request-scoped work."""

    settings: RlsSessionSettings
    active: bool = False
    metadata: dict[str, object] = field(default_factory=dict)

    def __enter__(self) -> "ScopedSession":
        self.active = True
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.active = False
        return False


def build_rls_session_settings(context: TenantRequestContext) -> RlsSessionSettings:
    """Translate the tenant context into SQL session variables."""

    return RlsSessionSettings(
        tenant_id=context.tenant_id,
        actor_role=context.actor_role,
        actor_subject=context.actor_subject,
        request_id=context.request_id,
        origin=context.origin,
    )


@contextmanager
def open_scoped_session(context: TenantRequestContext) -> Iterator[ScopedSession]:
    """Context manager that exposes the RLS session contract."""

    session = ScopedSession(settings=build_rls_session_settings(context))
    try:
        with session:
            yield session
    finally:
        session.active = False
