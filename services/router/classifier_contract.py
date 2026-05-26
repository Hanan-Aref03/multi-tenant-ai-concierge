"""Classifier model server contract.

Mohammad owns this contract definition (router/consumer side).
Rayan owns the model server implementation that satisfies it.

--- CONTRACT SUMMARY ---

POST /classify
  Request:  { "tenant_id": "<tenant>", "message": "<user message>" }
  Response: { "intent": "<one of VALID_INTENTS>", "confidence": <float 0-1> }
  Errors:   422 on missing/invalid input; 503 if model artifact failed integrity check

GET /health
  Response: {
    "status": "ok" | "degraded",
    "model_loaded": true | false,
    "model_checksum_valid": true | false
  }
  Notes:
    - Returns 200 with status="degraded" when the model is loaded but checksum
      validation produced a warning.
    - Returns 503 when the model failed to load or the checksum is invalid
      (OPS-04: server must refuse traffic if the artifact is corrupt or missing).

--- OPS-04 INTEGRITY REQUIREMENT ---

The model server must perform the following on startup:
  1. Locate the model artifact (path from CLASSIFIER_MODEL_PATH env var).
  2. Compute SHA-256 of the artifact.
  3. Compare against the expected checksum stored in CLASSIFIER_MODEL_SHA256.
  4. If the file is missing OR the checksum does not match:
       - Log a CRITICAL-level error with the mismatch detail.
       - Return HTTP 503 on all /classify requests.
       - Return model_checksum_valid=false on /health.
  5. Only serve predictions when both model_loaded=true AND model_checksum_valid=true.
"""

import logging
from dataclasses import dataclass
from typing import Literal, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Canonical intent set — single source of truth shared with router.py
# ---------------------------------------------------------------------------

VALID_INTENTS = frozenset(
    {"greeting", "faq", "knowledge_search", "lead_capture", "escalation", "off_topic"}
)

IntentLiteral = Literal[
    "greeting", "faq", "knowledge_search", "lead_capture", "escalation", "off_topic"
]


# ---------------------------------------------------------------------------
# Contract types
# ---------------------------------------------------------------------------


@dataclass
class ClassifyRequest:
    """Request body for POST /classify."""
    tenant_id: str
    message: str


@dataclass
class ClassifyResponse:
    """Successful response from POST /classify."""
    intent: str       # must be one of VALID_INTENTS
    confidence: float  # 0.0 – 1.0

    def is_valid(self) -> bool:
        return self.intent in VALID_INTENTS and 0.0 <= self.confidence <= 1.0


@dataclass
class ClassifyHealthResponse:
    """Response from GET /health."""
    status: str             # "ok" | "degraded"
    model_loaded: bool
    model_checksum_valid: bool

    def is_serving(self) -> bool:
        """True only when the server is fit to serve predictions (OPS-04)."""
        return self.model_loaded and self.model_checksum_valid


# ---------------------------------------------------------------------------
# Health-check helper (called by router before trusting the server)
# ---------------------------------------------------------------------------


async def verify_classifier_health(
    classifier_url: str,
    timeout: float = 3.0,
) -> Optional[ClassifyHealthResponse]:
    """
    Ping the model server GET /health endpoint.

    Returns ``None`` if the server is unreachable or returns an unexpected
    response — the router should fall back to LLM classification in that case.

    Parameters
    ----------
    classifier_url :
        Base URL, e.g. ``"http://model-server:8001"``.
    timeout :
        HTTP request timeout in seconds.
    """
    try:
        import httpx

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(f"{classifier_url.rstrip('/')}/health")
            resp.raise_for_status()
            data = resp.json()

        health = ClassifyHealthResponse(
            status=data.get("status", "unknown"),
            model_loaded=bool(data.get("model_loaded", False)),
            model_checksum_valid=bool(data.get("model_checksum_valid", False)),
        )

        if not health.is_serving():
            logger.warning(
                "Classifier server health check failed: model_loaded=%s checksum_valid=%s",
                health.model_loaded, health.model_checksum_valid,
            )

        return health

    except Exception as exc:
        logger.warning("Classifier health check unreachable: %s", exc)
        return None
