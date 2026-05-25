"""Tenant table model and lifecycle primitives.

Hanan owns the tenant schema and RLS policies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TenantStatus(str, Enum):
    """Lifecycle states for a tenant."""

    PROVISIONING = "provisioning"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"
    DELETED = "deleted"


@dataclass(slots=True)
class TenantMember:
    """Member row scoped to one tenant."""

    member_id: str
    tenant_id: str
    email: str
    role: str
    invited_by: str | None = None
    active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)

    def touch(self) -> None:
        self.updated_at = _utcnow()


@dataclass(slots=True)
class Tenant:
    """Tenant identity, provisioning state, and membership list."""

    tenant_id: str
    slug: str
    display_name: str
    owner_email: str
    status: TenantStatus = TenantStatus.PROVISIONING
    provisioning_stage: str = "requested"
    metadata: dict[str, Any] = field(default_factory=dict)
    members: list[TenantMember] = field(default_factory=list)
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)

    def touch(self) -> None:
        self.updated_at = _utcnow()

    def activate(self) -> None:
        self.status = TenantStatus.ACTIVE
        self.provisioning_stage = "active"
        self.touch()

    def suspend(self, reason: str | None = None) -> None:
        self.status = TenantStatus.SUSPENDED
        self.provisioning_stage = "suspended"
        if reason:
            self.metadata["suspension_reason"] = reason
        self.touch()

    def archive(self) -> None:
        self.status = TenantStatus.ARCHIVED
        self.provisioning_stage = "archived"
        self.touch()

    def mark_deleted(self) -> None:
        self.status = TenantStatus.DELETED
        self.provisioning_stage = "deleted"
        self.touch()

    def add_member(self, member: TenantMember) -> TenantMember:
        if member.tenant_id != self.tenant_id:
            raise ValueError(
                f"Cannot add member for tenant {member.tenant_id!r} to tenant {self.tenant_id!r}"
            )
        self.members = [existing for existing in self.members if existing.email != member.email]
        self.members.append(member)
        self.touch()
        return member

    def find_member(self, email: str) -> TenantMember | None:
        for member in self.members:
            if member.email == email:
                return member
        return None

    def member_emails(self) -> tuple[str, ...]:
        return tuple(member.email for member in self.members)
