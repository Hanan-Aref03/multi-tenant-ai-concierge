"""Auth helpers for tenants, admins, and widget visitors.

Hanan owns JWT, RBAC, and RLS support.
Ali Faddel owns the widget token exchange contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
import base64
import hashlib
import hmac
import json
from typing import Mapping, Sequence
from urllib.parse import urlsplit


class SecurityError(ValueError):
    """Base class for security-related failures."""


class AccessDenied(SecurityError):
    """Raised when a principal is not allowed to perform an action."""


class WidgetTokenError(SecurityError):
    """Raised when a widget token is invalid or expired."""


class TenantRole(str, Enum):
    """Principal roles used by the platform spine."""

    PLATFORM_MANAGER = "platform_manager"
    TENANT_ADMIN = "tenant_admin"
    MEMBER = "member"
    WIDGET_VISITOR = "widget_visitor"
    SERVICE = "service"


class AccessOperation(str, Enum):
    """Operations that are checked before the platform mutates data."""

    PROVISION_TENANT = "provision_tenant"
    INVITE_MEMBER = "invite_member"
    SUSPEND_TENANT = "suspend_tenant"
    ERASE_TENANT = "erase_tenant"
    READ_TENANT = "read_tenant"
    WRITE_TENANT = "write_tenant"
    READ_CONTENT = "read_content"
    WRITE_CONTENT = "write_content"
    READ_CONVERSATION = "read_conversation"
    WRITE_CONVERSATION = "write_conversation"
    SAVE_LEAD = "save_lead"
    USE_WIDGET = "use_widget"


@dataclass(slots=True, frozen=True)
class Principal:
    """Authenticated actor that is operating on the platform."""

    subject: str
    role: TenantRole
    tenant_id: str | None = None
    email: str | None = None
    origin: str | None = None
    scopes: tuple[str, ...] = ()


@dataclass(slots=True, frozen=True)
class WidgetSession:
    """Verified widget session state."""

    tenant_id: str
    origin: str
    issuer: str
    subject: str
    issued_at: datetime
    expires_at: datetime


_ROLE_RULES: dict[TenantRole, set[AccessOperation]] = {
    TenantRole.PLATFORM_MANAGER: set(AccessOperation),
    TenantRole.TENANT_ADMIN: {
        AccessOperation.INVITE_MEMBER,
        AccessOperation.READ_TENANT,
        AccessOperation.WRITE_TENANT,
        AccessOperation.READ_CONTENT,
        AccessOperation.WRITE_CONTENT,
        AccessOperation.READ_CONVERSATION,
        AccessOperation.WRITE_CONVERSATION,
        AccessOperation.SAVE_LEAD,
        AccessOperation.USE_WIDGET,
    },
    TenantRole.MEMBER: {
        AccessOperation.READ_TENANT,
        AccessOperation.READ_CONTENT,
        AccessOperation.WRITE_CONTENT,
        AccessOperation.READ_CONVERSATION,
        AccessOperation.WRITE_CONVERSATION,
        AccessOperation.SAVE_LEAD,
        AccessOperation.USE_WIDGET,
    },
    TenantRole.WIDGET_VISITOR: {
        AccessOperation.READ_CONTENT,
        AccessOperation.WRITE_CONVERSATION,
        AccessOperation.SAVE_LEAD,
        AccessOperation.USE_WIDGET,
    },
    TenantRole.SERVICE: {
        AccessOperation.READ_CONTENT,
        AccessOperation.READ_CONVERSATION,
        AccessOperation.WRITE_CONVERSATION,
        AccessOperation.SAVE_LEAD,
    },
}


def _canonical_origin(origin: str) -> str:
    parsed = urlsplit(origin)
    if not parsed.scheme or not parsed.netloc:
        raise WidgetTokenError(f"Invalid widget origin: {origin!r}")
    return f"{parsed.scheme}://{parsed.netloc}"


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(f"{data}{padding}")


def _json_dumps(payload: Mapping[str, object]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sign(message: str, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).digest()
    return _b64url_encode(digest)


def authorize_platform_action(
    principal: Principal,
    operation: AccessOperation,
    tenant_id: str | None = None,
) -> Principal:
    """Authorize a privileged action and return the principal on success."""

    if principal.role == TenantRole.PLATFORM_MANAGER:
        return principal
    if tenant_id is not None and principal.tenant_id != tenant_id:
        raise AccessDenied(
            f"Cross-tenant access denied for {principal.subject!r}: {principal.tenant_id!r} -> {tenant_id!r}"
        )
    allowed = _ROLE_RULES.get(principal.role, set())
    if operation not in allowed:
        raise AccessDenied(
            f"{principal.role.value} is not allowed to perform {operation.value}"
        )
    return principal


def authorize_tenant_action(
    principal: Principal,
    tenant_id: str,
    operation: AccessOperation,
) -> Principal:
    """Authorize an action scoped to one tenant."""

    if principal.role == TenantRole.PLATFORM_MANAGER:
        return principal
    if principal.tenant_id != tenant_id:
        raise AccessDenied(
            f"Cross-tenant access denied for {principal.subject!r}: {principal.tenant_id!r} -> {tenant_id!r}"
        )
    allowed = _ROLE_RULES.get(principal.role, set())
    if operation not in allowed:
        raise AccessDenied(
            f"{principal.role.value} is not allowed to perform {operation.value}"
        )
    return principal


def mint_widget_token(
    *,
    tenant_id: str,
    origin: str,
    issuer: str,
    secret: str,
    ttl_seconds: int,
    subject: str | None = None,
    now: datetime | None = None,
) -> str:
    """Create a signed short-lived widget token."""

    issued_at = now or datetime.now(timezone.utc)
    canonical_origin = _canonical_origin(origin)
    payload = {
        "aud": "widget",
        "exp": int((issued_at + timedelta(seconds=ttl_seconds)).timestamp()),
        "iat": int(issued_at.timestamp()),
        "iss": issuer,
        "origin": canonical_origin,
        "sub": subject or f"widget:{tenant_id}",
        "tenant_id": tenant_id,
        "typ": "widget",
    }
    header = {"alg": "HS256", "typ": "JWT"}
    header_segment = _b64url_encode(_json_dumps(header))
    payload_segment = _b64url_encode(_json_dumps(payload))
    body = f"{header_segment}.{payload_segment}"
    signature = _sign(body, secret)
    return f"{body}.{signature}"


def verify_widget_token(
    token: str,
    *,
    secret: str,
    expected_issuer: str,
    allowed_origins: Sequence[str],
    expected_tenant_id: str | None = None,
    now: datetime | None = None,
) -> WidgetSession:
    """Validate a widget token and return the verified session."""

    parts = token.split(".")
    if len(parts) != 3:
        raise WidgetTokenError("Widget token must have three segments")
    header_segment, payload_segment, signature_segment = parts
    body = f"{header_segment}.{payload_segment}"
    expected_signature = _sign(body, secret)
    if not hmac.compare_digest(signature_segment, expected_signature):
        raise WidgetTokenError("Widget token signature mismatch")

    try:
        header = json.loads(_b64url_decode(header_segment))
        payload = json.loads(_b64url_decode(payload_segment))
    except (json.JSONDecodeError, ValueError) as exc:
        raise WidgetTokenError("Widget token payload could not be decoded") from exc

    if header.get("alg") != "HS256":
        raise WidgetTokenError("Unsupported widget token algorithm")
    if payload.get("iss") != expected_issuer:
        raise WidgetTokenError("Unexpected widget token issuer")
    if payload.get("aud") != "widget":
        raise WidgetTokenError("Unexpected widget token audience")

    verified_at = now or datetime.now(timezone.utc)
    issued_at = datetime.fromtimestamp(int(payload["iat"]), tz=timezone.utc)
    expires_at = datetime.fromtimestamp(int(payload["exp"]), tz=timezone.utc)
    if verified_at >= expires_at:
        raise WidgetTokenError("Widget token expired")

    origin = _canonical_origin(str(payload["origin"]))
    allowed_origin_set = {_canonical_origin(value) for value in allowed_origins}
    if origin not in allowed_origin_set:
        raise WidgetTokenError(f"Origin {origin!r} is not allowed")

    tenant_id = str(payload["tenant_id"])
    if expected_tenant_id is not None and tenant_id != expected_tenant_id:
        raise WidgetTokenError(
            f"Widget token tenant mismatch: expected {expected_tenant_id!r}, got {tenant_id!r}"
        )

    return WidgetSession(
        tenant_id=tenant_id,
        origin=origin,
        issuer=str(payload["iss"]),
        subject=str(payload["sub"]),
        issued_at=issued_at,
        expires_at=expires_at,
    )


def principal_from_widget_session(session: WidgetSession) -> Principal:
    """Convert a widget session into a widget visitor principal."""

    return Principal(
        subject=session.subject,
        role=TenantRole.WIDGET_VISITOR,
        tenant_id=session.tenant_id,
        origin=session.origin,
    )
