"""Guardrails sidecar HTTP shell."""

from __future__ import annotations

from fastapi import Depends, FastAPI, Response
from pydantic import BaseModel, Field

from apps.shared.service_auth import require_service_token
from apps.shared.tracing import attach_request_id, resolve_request_id
from services.guardrails.redaction import redact_text
from services.guardrails.rules import evaluate_platform_rules

app = FastAPI(title="Concierge Guardrails Sidecar", version="0.1.0")


class GuardrailsCheckRequest(BaseModel):
    tenant_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    tenant_policy: dict[str, object] | None = None


class GuardrailsCheckResponse(BaseModel):
    request_id: str
    allowed: bool
    decision: str
    reason: str
    redacted_message: str


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "guardrails"}


@app.post(
    "/v1/check",
    response_model=GuardrailsCheckResponse,
    dependencies=[Depends(require_service_token)],
)
def check(
    payload: GuardrailsCheckRequest,
    response: Response,
    request_id: str = Depends(resolve_request_id),
) -> GuardrailsCheckResponse:
    attach_request_id(response, request_id)
    redaction = redact_text(payload.message)
    guardrail = evaluate_platform_rules(payload.message)

    return GuardrailsCheckResponse(
        request_id=request_id,
        allowed=guardrail.allowed,
        decision=guardrail.decision,
        reason=guardrail.reason,
        redacted_message=redaction.text,
    )
