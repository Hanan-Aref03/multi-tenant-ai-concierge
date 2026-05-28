import json
import shutil
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apps.modelserver.app.artifacts import (
    ArtifactVerificationError,
    MODEL_CARD_PATH,
    compute_sha256,
    load_verified_classifier,
)
from apps.modelserver.app.classifier import ClassifyRequest, classify_with_model
from apps.modelserver.app.main import app


def test_successful_artifact_hash_verification() -> None:
    verified = load_verified_classifier()

    assert verified.artifact_sha256 == verified.model_card["artifact"]["sha256"]
    assert compute_sha256(verified.artifact_path) == verified.artifact_sha256
    assert hasattr(verified.model, "predict")
    assert hasattr(verified.model, "predict_proba")


def test_hash_mismatch_raises_error() -> None:
    model_card = json.loads(MODEL_CARD_PATH.read_text(encoding="utf-8"))
    original_artifact_path = MODEL_CARD_PATH.parent / model_card["artifact"]["path"]
    temp_root = MODEL_CARD_PATH.parent.parent.parent / "tmp"
    temp_root.mkdir(exist_ok=True)
    temp_dir = temp_root / f"modelserver-artifact-{uuid.uuid4().hex}"
    temp_dir.mkdir(exist_ok=False)

    copied_artifact_path = temp_dir / "concierge_classifier.joblib"
    model_card_path = temp_dir / "model_card.json"

    shutil.copyfile(original_artifact_path, copied_artifact_path)
    model_card["artifact"]["path"] = copied_artifact_path.name
    model_card["artifact"]["sha256"] = "0" * 64
    model_card_path.write_text(json.dumps(model_card), encoding="utf-8")

    with pytest.raises(ArtifactVerificationError, match="SHA-256"):
        load_verified_classifier(model_card_path)


def test_real_classification_response_contains_intent_and_confidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SERVICE_TOKEN", "expected")

    with TestClient(app) as client:
        response = client.post(
            "/v1/classify",
            headers={"Authorization": "Bearer expected"},
            json={
                "tenant_id": "tenant_a",
                "message": "I need help with support ticket #123 {{person name}} 123456789",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] in {
        "faq",
        "human_request",
        "other",
        "sales_or_leads",
        "spam",
        "support",
    }
    assert 0.0 <= body["confidence"] <= 1.0
    assert body["model_version"] != "stub"


class _LowConfidenceModel:
    def predict(self, messages: list[str]) -> list[str]:
        assert messages == ["What time are you open?"]
        return ["faq"]

    def predict_proba(self, messages: list[str]) -> list[list[float]]:
        assert messages == ["What time are you open?"]
        return [[0.55, 0.45]]


def test_low_confidence_returns_agent_route() -> None:
    response = classify_with_model(
        request_id="req-low-confidence",
        payload=ClassifyRequest(
            tenant_id="tenant_a",
            message="What time are you open?",
        ),
        model=_LowConfidenceModel(),
        model_card={
            "router_confidence_threshold": 0.9,
            "artifact": {"sha256": "test-model-version"},
        },
    )

    assert response.route == "agent"
    assert response.intent == "faq"
    assert response.confidence == 0.55
