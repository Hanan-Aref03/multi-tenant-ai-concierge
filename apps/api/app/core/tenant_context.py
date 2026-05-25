"""Request-scoped tenant_id handling.

Hanan owns the tenant boundary enforcement.
Mohammad uses this context in retrieval and agent flows.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from contextvars import ContextVar, Token
from datetime import datetime, timezone
from typing import Iterator
from uuid import uuid4

from apps.api.app.core.security import Principal


class TenantContextError(RuntimeError):
    """Raised when a tenant context is required but missing."""


@dataclass(slots=True)
class TenantRequestContext:
    """Per-request state that carries tenant identity and actor metadata."""

    tenant_id: str
    principal: Principal
    request_id: str = field(default_factory=lambda: f"req_{uuid4().hex[:12]}")
    origin: str | None = None
    source: str = "api"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def actor_role(self) -> str:
        return self.principal.role.value

    @property
    def actor_subject(self) -> str:
        return self.principal.subject

    def as_rls_context(self) -> dict[str, str]:
        return {
            "app.tenant_id": self.tenant_id,
            "app.actor_role": self.actor_role,
            "app.actor_subject": self.actor_subject,
            "app.request_id": self.request_id,
        }


_current_context: ContextVar[TenantRequestContext | None] = ContextVar(
    "current_tenant_context",
    default=None,
)


def set_current_tenant_context(context: TenantRequestContext) -> Token[TenantRequestContext | None]:
    """Store the active tenant context for the current task."""

    return _current_context.set(context)


def reset_current_tenant_context(token: Token[TenantRequestContext | None]) -> None:
    """Restore the previous tenant context."""

    _current_context.reset(token)


def get_current_tenant_context() -> TenantRequestContext:
    """Return the active tenant context or fail loudly."""

    context = _current_context.get()
    if context is None:
        raise TenantContextError("No tenant context is active")
    return context


def get_current_tenant_id() -> str:
    """Return the active tenant id."""

    return get_current_tenant_context().tenant_id


@contextmanager
def tenant_context(context: TenantRequestContext) -> Iterator[TenantRequestContext]:
    """Context manager that sets and restores the tenant scope."""

    token = set_current_tenant_context(context)
    try:
        yield context
    finally:
        reset_current_tenant_context(token)
