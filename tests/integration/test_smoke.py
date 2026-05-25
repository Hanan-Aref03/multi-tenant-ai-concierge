"""End-to-end smoke test lane.

Hanan owns the backend flow integration.
Ali Faddel owns the UI surfaces that the smoke test touches.
"""

from __future__ import annotations

import unittest

from apps.api.app.api.v1.tenants import TenantInviteRequest, TenantProvisionRequest
from apps.api.app.core.security import Principal, TenantRole
from apps.api.app.main import build_platform_application


class SmokeTests(unittest.TestCase):
    def test_platform_spine_happy_path(self) -> None:
        platform = build_platform_application()
        owner = Principal(subject="hanan", role=TenantRole.PLATFORM_MANAGER)

        tenant = platform.tenant_service.provision_tenant(
            TenantProvisionRequest(
                slug="acme-health",
                display_name="Acme Health",
                owner_email="owner@acme.example",
            ),
            owner,
        )

        admin = Principal(
            subject="owner@acme.example",
            role=TenantRole.TENANT_ADMIN,
            tenant_id=tenant.tenant_id,
        )
        platform.tenant_service.invite_member(
            tenant.tenant_id,
            TenantInviteRequest(email="member@acme.example", role="member"),
            admin,
        )

        report = platform.refresh_health_report()
        summary = platform.summary()

        self.assertTrue(report.ready)
        self.assertEqual(report.tenant_count, 1)
        self.assertEqual(report.audit_event_count, 2)
        self.assertEqual(summary["tenants"], 1)
        self.assertGreaterEqual(summary["implemented_routes"], 6)
        self.assertIn("Hanan", {route.owner for route in platform.route_catalog.routes})
        self.assertIn("Ali Faddel", {route.owner for route in platform.route_catalog.routes})
        self.assertIn("Mohammad", {route.owner for route in platform.route_catalog.routes})


if __name__ == "__main__":
    unittest.main()
