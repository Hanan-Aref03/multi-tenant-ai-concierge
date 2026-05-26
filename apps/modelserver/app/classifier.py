"""Classifier inference helpers.

Rayan owns the routing model and its evaluation contract.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ClassifyRequest(BaseModel):
    tenant_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)


class ClassifyResponse(BaseModel):
    request_id: str
    route: str
    intent: str
    confidence: float
    model_version: str


def classify_stub(request_id: str, _: ClassifyRequest) -> ClassifyResponse:
    """Return the current fallback routing contract."""

    return ClassifyResponse(
        request_id=request_id,
        route="agent",
        intent="needs_agent_review",
        confidence=0.0,
        model_version="stub",
    )
