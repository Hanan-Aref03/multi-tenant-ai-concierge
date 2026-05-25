"""Security test lane for tenant isolation.

Hanan owns the RLS and request-bound tenant checks.
Mohammad owns the repository scoping and retrieval filters.
"""

from __future__ import annotations

from pathlib import Path
import unittest

from apps.api.app.core.security import (
    AccessDenied,
    AccessOperation,
    Principal,
    TenantRole,
    authorize_tenant_action,
)
from apps.api.app.core.tenant_context import TenantRequestContext
from apps.api.app.db.models.content import ContentDocument, ContentKind
from apps.api.app.db.models.tenant import Tenant
from apps.api.app.db.repository import InMemoryPlatformRepository
from apps.api.app.db.session import build_rls_session_settings


class TenantIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = InMemoryPlatformRepository()
        self.repository.save_tenant(
            Tenant(
                tenant_id="tenant-a",
                slug="tenant-a",
                display_name="Tenant A",
                owner_email="owner@a.example",
            )
        )
        self.repository.save_tenant(
            Tenant(
                tenant_id="tenant-b",
                slug="tenant-b",
                display_name="Tenant B",
                owner_email="owner@b.example",
            )
        )

    def test_repository_keeps_tenant_documents_isolated(self) -> None:
        self.repository.save_document(
            ContentDocument(
                tenant_id="tenant-a",
                document_id="doc-a",
                title="Tenant A FAQ",
                body="Tenant A content",
                kind=ContentKind.FAQ,
            )
        )
        self.repository.save_document(
            ContentDocument(
                tenant_id="tenant-b",
                document_id="doc-b",
                title="Tenant B FAQ",
                body="Tenant B content",
                kind=ContentKind.FAQ,
            )
        )

        self.assertEqual(self.repository.tenant_document_titles("tenant-a"), ["Tenant A FAQ"])
        self.assertEqual(self.repository.tenant_document_titles("tenant-b"), ["Tenant B FAQ"])

    def test_cross_tenant_action_is_denied(self) -> None:
        principal = Principal(
            subject="member-a",
            role=TenantRole.TENANT_ADMIN,
            tenant_id="tenant-a",
        )

        with self.assertRaises(AccessDenied):
            authorize_tenant_action(principal, "tenant-b", AccessOperation.READ_CONTENT)

    def test_rls_session_settings_include_tenant_context(self) -> None:
        principal = Principal(
            subject="member-a",
            role=TenantRole.TENANT_ADMIN,
            tenant_id="tenant-a",
        )
        context = TenantRequestContext(
            tenant_id="tenant-a",
            principal=principal,
            request_id="req-123",
            origin="http://localhost:5173",
        )

        session_settings = build_rls_session_settings(context)

        self.assertEqual(session_settings.as_postgres_settings()["app.tenant_id"], "tenant-a")
        self.assertIn("SELECT set_config('app.tenant_id'", session_settings.as_sql_prologue()[0])

    def test_rls_migration_contains_policy_markers(self) -> None:
        root = Path(__file__).resolve().parents[2]
        migration = root / "infrastructure" / "postgres" / "migrations" / "0002_rls.sql"
        sql = migration.read_text(encoding="utf-8")

        self.assertIn("ENABLE ROW LEVEL SECURITY", sql)
        self.assertIn("FORCE ROW LEVEL SECURITY", sql)
        self.assertIn("app.current_tenant_id()", sql)
        self.assertIn("WITH CHECK (app.has_tenant_access(tenant_id))", sql)


if __name__ == "__main__":
    unittest.main()
