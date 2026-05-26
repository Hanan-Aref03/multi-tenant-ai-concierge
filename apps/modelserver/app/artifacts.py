"""Artifact validation helpers.

Rayan owns the artifact hash and model-card checks.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib

MODEL_DIR = Path(__file__).resolve().parents[1] / "artifacts" / "model"
MODEL_CARD_PATH = MODEL_DIR / "model_card.json"


@dataclass(frozen=True)
class VerifiedClassifier:
    model: Any
    model_card: dict[str, Any]
    artifact_path: Path
    artifact_sha256: str


class ArtifactVerificationError(RuntimeError):
    """Raised when a model artifact fails integrity validation."""


def compute_sha256(path: Path) -> str:
    """Return the SHA-256 digest for an artifact without loading it."""

    digest = hashlib.sha256()
    with path.open("rb") as artifact:
        for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_model_card(model_card_path: Path = MODEL_CARD_PATH) -> dict[str, Any]:
    """Load the model card JSON that declares the expected artifact digest."""

    with model_card_path.open("r", encoding="utf-8") as model_card_file:
        model_card = json.load(model_card_file)

    if not isinstance(model_card, dict):
        raise ArtifactVerificationError("model_card.json must contain a JSON object")

    return model_card


def _artifact_metadata(model_card: dict[str, Any]) -> tuple[str, str]:
    artifact = model_card.get("artifact")
    if not isinstance(artifact, dict):
        raise ArtifactVerificationError("model_card.json is missing artifact metadata")

    artifact_path = artifact.get("path")
    expected_sha256 = artifact.get("sha256")
    if not isinstance(artifact_path, str) or not artifact_path:
        raise ArtifactVerificationError("model_card.json artifact.path is required")
    if not isinstance(expected_sha256, str) or not expected_sha256:
        raise ArtifactVerificationError("model_card.json artifact.sha256 is required")

    return artifact_path, expected_sha256


def load_verified_classifier(
    model_card_path: Path = MODEL_CARD_PATH,
) -> VerifiedClassifier:
    """Verify the model-card hash and then load the joblib classifier."""

    model_card = load_model_card(model_card_path)
    artifact_path_value, expected_sha256 = _artifact_metadata(model_card)
    artifact_path = model_card_path.parent / artifact_path_value

    actual_sha256 = compute_sha256(artifact_path)
    if actual_sha256 != expected_sha256:
        raise ArtifactVerificationError(
            "Classifier artifact SHA-256 does not match model_card.json"
        )

    model = joblib.load(artifact_path)
    return VerifiedClassifier(
        model=model,
        model_card=model_card,
        artifact_path=artifact_path,
        artifact_sha256=actual_sha256,
    )
