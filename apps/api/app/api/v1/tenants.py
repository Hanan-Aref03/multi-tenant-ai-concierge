"""Tenant lifecycle endpoints.

Hanan owns provisioning, suspension, and deletion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from apps.api.app.core.security import (
    AccessOperation,
    Principal,
    TenantRole,
    authorize_platform_action,
    authorize_tenant_action,
)
from apps.api.app.core.config import AppSettings, get_settings
from apps.api.app.db.models.tenant import Tenant, TenantMember
from apps.api.app.db.repository import InMemoryPlatformRepository, TenantSnapshot
from apps.api.app.services.audit_service import AuditTrail


@dataclass(slots=True)
class TenantProvisionRequest:
    """Input for provisioning a brand new tenant."""

    slug: str
    display_name: str
    owner_email: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TenantInviteRequest:
    """Input for inviting a new member to a tenant."""

    email: str
    role: str = "member"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TenantPlatformService:
    """Orchestrates tenant lifecycle actions with audit logging."""

    repository: InMemoryPlatformRepository
    audit_trail: AuditTrail
    settings: AppSettings = field(default_factory=get_settings)

    def provision_tenant(
        self,
        request: TenantProvisionRequest,
        principal: Principal,
    ) -> Tenant:
        authorize_platform_action(principal, AccessOperation.PROVISION_TENANT)
        tenant_id = f"tenant_{uuid4().hex[:12]}"
        tenant = Tenant(
            tenant_id=tenant_id,
            slug=request.slug,
            display_name=request.display_name,
            owner_email=request.owner_email,
            metadata=dict(request.metadata),
        )
        tenant.activate()
        self.repository.save_tenant(tenant)

        owner_member = TenantMember(
            member_id=f"member_{uuid4().hex[:12]}",
            tenant_id=tenant_id,
            email=request.owner_email,
            role=TenantRole.TENANT_ADMIN.value,
            invited_by=principal.subject,
            metadata={"seed_role": "owner"},
        )
        self.repository.upsert_member(tenant_id, owner_member)
        self.audit_trail.record_action(
            tenant_id=tenant_id,
            actor=principal.subject,
            action="tenant.provisioned",
            resource_type="tenant",
            resource_id=tenant_id,
            details={
                "slug": request.slug,
                "display_name": request.display_name,
                "owner_email": request.owner_email,
            },
        )
        return self.repository.get_tenant(tenant_id)

    def invite_member(
        self,
        tenant_id: str,
        request: TenantInviteRequest,
        principal: Principal,
    ) -> TenantMember:
        authorize_tenant_action(principal, tenant_id, AccessOperation.INVITE_MEMBER)
        tenant = self.repository.get_tenant(tenant_id)
        member = TenantMember(
            member_id=f"member_{uuid4().hex[:12]}",
            tenant_id=tenant_id,
            email=request.email,
            role=request.role,
            invited_by=principal.subject,
            metadata=dict(request.metadata),
        )
        tenant.add_member(member)
        self.repository.save_tenant(tenant)
        self.audit_trail.record_action(
            tenant_id=tenant_id,
            actor=principal.subject,
            action="tenant.member.invited",
            resource_type="tenant_member",
            resource_id=member.member_id,
            details={"email": request.email, "role": request.role},
        )
        return member

    def suspend_tenant(
        self,
        tenant_id: str,
        principal: Principal,
        *,
        reason: str = "",
    ) -> Tenant:
        authorize_platform_action(principal, AccessOperation.SUSPEND_TENANT, tenant_id)
        tenant = self.repository.get_tenant(tenant_id)
        tenant.suspend(reason=reason or None)
        self.repository.save_tenant(tenant)
        self.audit_trail.record_action(
            tenant_id=tenant_id,
            actor=principal.subject,
            action="tenant.suspended",
            resource_type="tenant",
            resource_id=tenant_id,
            details={"reason": reason},
        )
        return tenant

    def erase_tenant(
        self,
        tenant_id: str,
        principal: Principal,
        *,
        reason: str = "",
    ) -> dict[str, int]:
        authorize_platform_action(principal, AccessOperation.ERASE_TENANT, tenant_id)
        erased = self.repository.erase_tenant(tenant_id)
        self.audit_trail.record_action(
            tenant_id=tenant_id,
            actor=principal.subject,
            action="tenant.erased",
            resource_type="tenant",
            resource_id=tenant_id,
            details={"reason": reason, **erased},
        )
        return erased

    def snapshot(self, tenant_id: str) -> TenantSnapshot:
        return self.repository.snapshot(tenant_id)

    def describe_tenant(self, tenant_id: str) -> dict[str, Any]:
        snapshot = self.snapshot(tenant_id)
        return {
            "tenant_id": snapshot.tenant_id,
            "slug": snapshot.slug,
            "display_name": snapshot.display_name,
            "status": snapshot.status.value,
            "members": snapshot.members,
            "documents": snapshot.documents,
            "conversations": snapshot.conversations,
            "leads": snapshot.leads,
        }
