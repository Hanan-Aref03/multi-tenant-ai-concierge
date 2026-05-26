"""Lean model server entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Depends, FastAPI, Request, Response

from apps.modelserver.app.artifacts import load_verified_classifier
from apps.modelserver.app.classifier import (
    ClassifyRequest,
    ClassifyResponse,
    classify_with_model,
)
from apps.shared.service_auth import require_service_token
from apps.shared.tracing import attach_request_id, resolve_request_id


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    verified_classifier = load_verified_classifier()
    app.state.classifier_model = verified_classifier.model
    app.state.model_card = verified_classifier.model_card
    app.state.artifact_sha256 = verified_classifier.artifact_sha256
    app.state.model_loaded = True
    app.state.model_checksum_valid = True
    yield


app = FastAPI(
    title="Concierge Model Server",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "modelserver"}


@app.get("/health")
def health(request: Request) -> dict[str, object]:
    return {
        "status": "ok",
        "model_loaded": bool(getattr(request.app.state, "model_loaded", False)),
        "model_checksum_valid": bool(getattr(request.app.state, "model_checksum_valid", False)),
    }


@app.post(
    "/v1/classify",
    response_model=ClassifyResponse,
    dependencies=[Depends(require_service_token)],
)
def classify(
    payload: ClassifyRequest,
    request: Request,
    response: Response,
    request_id: str = Depends(resolve_request_id),
) -> ClassifyResponse:
    attach_request_id(response, request_id)
    return classify_with_model(
        request_id=request_id,
        payload=payload,
        model=request.app.state.classifier_model,
        model_card=request.app.state.model_card,
    )
