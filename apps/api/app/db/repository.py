"""In-memory repository primitives for the Hanan platform spine.

This repository layer is intentionally tiny and dependency-free so the
platform can be exercised before the full database stack is wired in.
The SQL migrations still define the production schema and RLS behavior.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List

from apps.api.app.db.models.content import ContentDocument
from apps.api.app.db.models.conversation import Conversation
from apps.api.app.db.models.lead import Lead
from apps.api.app.db.models.tenant import Tenant, TenantMember, TenantStatus


@dataclass(slots=True)
class TenantSnapshot:
    tenant_id: str
    slug: str
    display_name: str
    status: TenantStatus
    members: int
    documents: int
    conversations: int
    leads: int


@dataclass(slots=True)
class InMemoryPlatformRepository:
    tenants: Dict[str, Tenant] = field(default_factory=dict)
    documents: Dict[str, Dict[str, ContentDocument]] = field(default_factory=dict)
    conversations: Dict[str, Dict[str, Conversation]] = field(default_factory=dict)
    leads: Dict[str, Dict[str, Lead]] = field(default_factory=dict)

    def save_tenant(self, tenant: Tenant) -> Tenant:
        self.tenants[tenant.tenant_id] = tenant
        self.documents.setdefault(tenant.tenant_id, {})
        self.conversations.setdefault(tenant.tenant_id, {})
        self.leads.setdefault(tenant.tenant_id, {})
        return tenant

    def get_tenant(self, tenant_id: str) -> Tenant:
        try:
            return self.tenants[tenant_id]
        except KeyError as exc:
            raise KeyError(f"Unknown tenant: {tenant_id}") from exc

    def list_tenants(self) -> List[Tenant]:
        return sorted(self.tenants.values(), key=lambda tenant: tenant.created_at)

    def upsert_member(self, tenant_id: str, member: TenantMember) -> Tenant:
        tenant = self.get_tenant(tenant_id)
        tenant.add_member(member)
        return self.save_tenant(tenant)

    def save_document(self, document: ContentDocument) -> ContentDocument:
        self.documents.setdefault(document.tenant_id, {})[document.document_id] = document
        return document

    def save_conversation(self, conversation: Conversation) -> Conversation:
        self.conversations.setdefault(conversation.tenant_id, {})[conversation.conversation_id] = conversation
        return conversation

    def save_lead(self, lead: Lead) -> Lead:
        self.leads.setdefault(lead.tenant_id, {})[lead.lead_id] = lead
        return lead

    def erase_tenant(self, tenant_id: str) -> dict[str, int]:
        tenant = self.tenants.pop(tenant_id, None)
        members = 0
        documents = len(self.documents.pop(tenant_id, {}))
        conversations = len(self.conversations.pop(tenant_id, {}))
        leads = len(self.leads.pop(tenant_id, {}))
        if tenant is not None:
            members = len(tenant.members)
        return {
            "tenants": 1 if tenant is not None else 0,
            "members": members,
            "documents": documents,
            "conversations": conversations,
            "leads": leads,
        }

    def snapshot(self, tenant_id: str) -> TenantSnapshot:
        tenant = self.get_tenant(tenant_id)
        return TenantSnapshot(
            tenant_id=tenant.tenant_id,
            slug=tenant.slug,
            display_name=tenant.display_name,
            status=tenant.status,
            members=len(tenant.members),
            documents=len(self.documents.get(tenant_id, {})),
            conversations=len(self.conversations.get(tenant_id, {})),
            leads=len(self.leads.get(tenant_id, {})),
        )

    def tenant_document_titles(self, tenant_id: str) -> list[str]:
        return [document.title for document in self.documents.get(tenant_id, {}).values()]

    def tenant_conversations(self, tenant_id: str) -> list[Conversation]:
        return list(self.conversations.get(tenant_id, {}).values())

    def tenant_leads(self, tenant_id: str) -> list[Lead]:
        return list(self.leads.get(tenant_id, {}).values())
