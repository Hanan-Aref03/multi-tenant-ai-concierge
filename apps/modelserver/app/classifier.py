"""Classifier inference helpers.

Rayan owns the routing model and its evaluation contract.
"""

from __future__ import annotations

import re
from typing import Any

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


TEMPLATE_RE = re.compile(r"\{\{.*?\}\}")
HASH_ID_RE = re.compile(r"#\d+\b")
LONG_NUMBER_RE = re.compile(r"\b\d{5,}\b")
SPACE_RE = re.compile(r"\s+")


ROUTE_BY_INTENT = {
    "spam": "drop",
    "faq": "rag",
    "sales_or_leads": "capture_lead",
    "human_request": "escalate",
    "support": "support",
    "other": "agent",
}


def clean_message(message: str) -> str:
    """Mirror the training-time cleanup used before classifier inference."""

    cleaned = TEMPLATE_RE.sub(" ", message)
    cleaned = HASH_ID_RE.sub(" ", cleaned)
    cleaned = LONG_NUMBER_RE.sub(" ", cleaned)
    return SPACE_RE.sub(" ", cleaned).strip()


def _confidence_from_predict_proba(model: Any, cleaned_message: str) -> float:
    probabilities = model.predict_proba([cleaned_message])
    return float(max(probabilities[0]))


def _model_version(model_card: dict[str, Any]) -> str:
    artifact = model_card.get("artifact")
    if isinstance(artifact, dict) and isinstance(artifact.get("sha256"), str):
        return artifact["sha256"]

    model_name = model_card.get("model_name")
    if isinstance(model_name, str) and model_name:
        return model_name

    return "unknown"


def _router_threshold(model_card: dict[str, Any]) -> float:
    threshold = model_card.get("router_confidence_threshold", 0.65)
    if isinstance(threshold, int | float):
        return float(threshold)
    return 0.65


def classify_with_model(
    request_id: str,
    payload: ClassifyRequest,
    model: Any,
    model_card: dict[str, Any],
) -> ClassifyResponse:
    """Classify a request with the verified sklearn pipeline."""

    cleaned_message = clean_message(payload.message)
    intent = str(model.predict([cleaned_message])[0])
    confidence = _confidence_from_predict_proba(model, cleaned_message)
    threshold = _router_threshold(model_card)
    route = "agent" if confidence < threshold else ROUTE_BY_INTENT.get(intent, "agent")

    return ClassifyResponse(
        request_id=request_id,
        route=route,
        intent=intent,
        confidence=confidence,
        model_version=_model_version(model_card),
    )
