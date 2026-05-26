"""Artifact validation helpers."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib


@dataclass(frozen=True)
class ArtifactMetadata:
    """Minimal model artifact metadata."""

    name: str
    version: str
    model_hash: str
    model_card: str | None = None


@dataclass(frozen=True)
class ArtifactValidationResult:
    """Validation outcome for a model artifact bundle."""

    ok: bool
    reason: str


def compute_sha256(payload: bytes) -> str:
    """Return the hex SHA-256 digest for a payload."""

    return hashlib.sha256(payload).hexdigest()


def validate_artifact(metadata: ArtifactMetadata, expected_name: str) -> ArtifactValidationResult:
    """Validate the basic metadata contract before serving a model artifact."""

    if not metadata.name.strip():
        return ArtifactValidationResult(ok=False, reason="artifact name is required")
    if metadata.name != expected_name:
        return ArtifactValidationResult(
            ok=False,
            reason=f"unexpected artifact name '{metadata.name}'",
        )
    if not metadata.version.strip():
        return ArtifactValidationResult(ok=False, reason="artifact version is required")
    if len(metadata.model_hash.strip()) < 16:
        return ArtifactValidationResult(ok=False, reason="artifact hash is too short")
    if metadata.model_card is not None and not metadata.model_card.strip():
        return ArtifactValidationResult(ok=False, reason="artifact model card cannot be empty")

    return ArtifactValidationResult(ok=True, reason="artifact metadata is valid")
