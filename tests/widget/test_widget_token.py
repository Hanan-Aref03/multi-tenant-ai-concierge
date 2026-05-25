"""Widget token and origin tests.

Ali Faddel owns the widget flow.
Hanan owns the signed token validation and server-side origin checks.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from apps.api.app.core.security import WidgetTokenError, mint_widget_token, verify_widget_token


class WidgetTokenTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 5, 25, tzinfo=timezone.utc)
        self.secret = "test-secret"

    def test_widget_token_round_trip(self) -> None:
        token = mint_widget_token(
            tenant_id="tenant-a",
            origin="http://localhost:5173",
            issuer="concierge-widget",
            secret=self.secret,
            ttl_seconds=300,
            now=self.now,
        )

        session = verify_widget_token(
            token,
            secret=self.secret,
            expected_issuer="concierge-widget",
            allowed_origins=("http://localhost:5173",),
            expected_tenant_id="tenant-a",
            now=self.now + timedelta(seconds=30),
        )

        self.assertEqual(session.tenant_id, "tenant-a")
        self.assertEqual(session.origin, "http://localhost:5173")
        self.assertEqual(session.subject, "widget:tenant-a")

    def test_expired_widget_token_is_rejected(self) -> None:
        token = mint_widget_token(
            tenant_id="tenant-a",
            origin="http://localhost:5173",
            issuer="concierge-widget",
            secret=self.secret,
            ttl_seconds=1,
            now=self.now,
        )

        with self.assertRaises(WidgetTokenError):
            verify_widget_token(
                token,
                secret=self.secret,
                expected_issuer="concierge-widget",
                allowed_origins=("http://localhost:5173",),
                now=self.now + timedelta(seconds=2),
            )

    def test_cross_tenant_widget_token_is_rejected(self) -> None:
        token = mint_widget_token(
            tenant_id="tenant-a",
            origin="http://localhost:5173",
            issuer="concierge-widget",
            secret=self.secret,
            ttl_seconds=300,
            now=self.now,
        )

        with self.assertRaises(WidgetTokenError):
            verify_widget_token(
                token,
                secret=self.secret,
                expected_issuer="concierge-widget",
                allowed_origins=("http://localhost:5173",),
                expected_tenant_id="tenant-b",
                now=self.now + timedelta(seconds=1),
            )

    def test_disallowed_origin_is_rejected(self) -> None:
        token = mint_widget_token(
            tenant_id="tenant-a",
            origin="http://localhost:5173",
            issuer="concierge-widget",
            secret=self.secret,
            ttl_seconds=300,
            now=self.now,
        )

        with self.assertRaises(WidgetTokenError):
            verify_widget_token(
                token,
                secret=self.secret,
                expected_issuer="concierge-widget",
                allowed_origins=("http://example.com",),
                now=self.now + timedelta(seconds=1),
            )

    def test_tampered_signature_is_rejected(self) -> None:
        token = mint_widget_token(
            tenant_id="tenant-a",
            origin="http://localhost:5173",
            issuer="concierge-widget",
            secret=self.secret,
            ttl_seconds=300,
            now=self.now,
        )
        tampered = token[:-1] + ("A" if token[-1] != "A" else "B")

        with self.assertRaises(WidgetTokenError):
            verify_widget_token(
                tampered,
                secret=self.secret,
                expected_issuer="concierge-widget",
                allowed_origins=("http://localhost:5173",),
                now=self.now + timedelta(seconds=1),
            )


if __name__ == "__main__":
    unittest.main()
