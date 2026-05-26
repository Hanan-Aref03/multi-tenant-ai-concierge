"""Widget JWT auth dependency — verifies Bearer token on every chat request.

tenant_id is extracted from the verified token ONLY. Never from request body.
"""
import uuid

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.services.widget_token import verify_widget_token

_bearer = HTTPBearer(auto_error=False)


class WidgetTokenClaims:
    def __init__(self, tenant_id: uuid.UUID, widget_id: str, conversation_id: uuid.UUID, origin: str):
        self.tenant_id = tenant_id
        self.widget_id = widget_id
        self.conversation_id = conversation_id
        self.origin = origin


async def require_widget_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> WidgetTokenClaims:
    """FastAPI dependency. Raises 401 if token is missing, expired, or invalid."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="Token missing")
    try:
        claims = verify_widget_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token invalid")

    return WidgetTokenClaims(
        tenant_id=uuid.UUID(claims["tenant_id"]),
        widget_id=claims["widget_id"],
        conversation_id=uuid.UUID(claims["conversation_id"]),
        origin=claims["origin"],
    )
