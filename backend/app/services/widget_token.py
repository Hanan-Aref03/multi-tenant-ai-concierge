"""Widget JWT service — issue and verify short-lived per-widget session tokens.

tenant_id is ALWAYS derived from the verified token. Never trust the request body.
"""
import uuid
from datetime import UTC, datetime, timedelta

import jwt

from app.config import get_settings

settings = get_settings()

_ALGORITHM = "HS256"


def issue_widget_token(
    tenant_id: uuid.UUID,
    widget_id: str,
    conversation_id: uuid.UUID,
    origin: str,
) -> str:
    now = datetime.now(UTC)
    exp = now + timedelta(seconds=settings.widget_token_expire_seconds)
    payload = {
        "tenant_id": str(tenant_id),
        "widget_id": widget_id,
        "conversation_id": str(conversation_id),
        "origin": origin,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=_ALGORITHM)


def verify_widget_token(token: str) -> dict:
    """Decode and verify a widget session JWT.

    Raises jwt.PyJWTError (including ExpiredSignatureError) on failure.
    Callers must catch and convert to HTTP 401.
    """
    return jwt.decode(token, settings.secret_key, algorithms=[_ALGORITHM])
