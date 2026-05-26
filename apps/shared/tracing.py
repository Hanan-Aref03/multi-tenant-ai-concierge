"""Minimal request ID propagation helpers."""

from __future__ import annotations

from typing import Annotated
from uuid import uuid4

from fastapi import Header, Response

REQUEST_ID_HEADER = "X-Request-ID"


def resolve_request_id(
    x_request_id: Annotated[str | None, Header(alias=REQUEST_ID_HEADER)] = None,
) -> str:
    """Use the incoming request ID when present, otherwise generate one."""

    request_id = x_request_id.strip() if x_request_id else ""
    return request_id or str(uuid4())


def attach_request_id(response: Response, request_id: str) -> None:
    """Mirror the request ID into the response header."""

    response.headers[REQUEST_ID_HEADER] = request_id
