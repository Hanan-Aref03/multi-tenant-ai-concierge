"""Core platform primitives for auth, context, and config."""

from apps.api.app.core.config import AppSettings, get_settings
from apps.api.app.core.security import (
    AccessDenied,
    AccessOperation,
    Principal,
    TenantRole,
    WidgetSession,
    WidgetTokenError,
    authorize_platform_action,
    authorize_tenant_action,
    mint_widget_token,
    principal_from_widget_session,
    verify_widget_token,
)
from apps.api.app.core.tenant_context import (
    TenantContextError,
    TenantRequestContext,
    get_current_tenant_context,
    get_current_tenant_id,
    tenant_context,
)

__all__ = [
    "AccessDenied",
    "AccessOperation",
    "AppSettings",
    "Principal",
    "TenantContextError",
    "TenantRequestContext",
    "TenantRole",
    "WidgetSession",
    "WidgetTokenError",
    "authorize_platform_action",
    "authorize_tenant_action",
    "get_current_tenant_context",
    "get_current_tenant_id",
    "get_settings",
    "mint_widget_token",
    "principal_from_widget_session",
    "tenant_context",
    "verify_widget_token",
]
