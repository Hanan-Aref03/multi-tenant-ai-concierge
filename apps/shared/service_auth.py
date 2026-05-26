"""Service-to-service bearer token authentication helpers."""

from __future__ import annotations

import hmac
import os
from typing import Annotated

from fastapi import Header, HTTPException, status

SERVICE_TOKEN_ENV = "SERVICE_TOKEN"
LOCAL_TEST_SERVICE_TOKEN = "local-test-service-token"


def get_service_token() -> str:
    """Return the configured service token, using a default only under pytest."""

    token = os.getenv(SERVICE_TOKEN_ENV)
    if token:
        return token

    if os.getenv("PYTEST_CURRENT_TEST"):
        return LOCAL_TEST_SERVICE_TOKEN

    raise RuntimeError(f"{SERVICE_TOKEN_ENV} is required for service endpoints")


def require_service_token(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> None:
    """FastAPI dependency that requires Authorization: Bearer <SERVICE_TOKEN>."""

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer service token",
        )

    supplied_token = authorization.removeprefix("Bearer ").strip()

    try:
        expected_token = get_service_token()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service token is not configured",
        ) from exc

    if not supplied_token or not hmac.compare_digest(supplied_token, expected_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid service token",
        )
