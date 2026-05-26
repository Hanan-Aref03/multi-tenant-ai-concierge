"""Lean model server entrypoint."""

from __future__ import annotations

from fastapi import Depends, FastAPI, Response

from apps.modelserver.app.classifier import (
    ClassifyRequest,
    ClassifyResponse,
    classify_stub,
)
from apps.shared.service_auth import require_service_token
from apps.shared.tracing import attach_request_id, resolve_request_id

app = FastAPI(title="Concierge Model Server", version="0.1.0")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "modelserver"}


@app.post(
    "/v1/classify",
    response_model=ClassifyResponse,
    dependencies=[Depends(require_service_token)],
)
def classify(
    payload: ClassifyRequest,
    response: Response,
    request_id: str = Depends(resolve_request_id),
) -> ClassifyResponse:
    attach_request_id(response, request_id)
    return classify_stub(request_id, payload)
