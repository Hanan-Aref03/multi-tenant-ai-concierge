"""Classifier modelserver client."""

import logging
from typing import Optional

from apps.shared.service_auth import get_service_token
from services.router.constants import INTENTS, MODELSERVER_INTENT_MAP
from services.router.contracts import ClassifyResult

logger = logging.getLogger(__name__)


def normalize_classifier_intent(label: str) -> str:
    """Map modelserver labels onto router-owned intent names in one place."""
    normalized = str(label or "").strip().lower()
    return MODELSERVER_INTENT_MAP.get(normalized, normalized)


async def _call_classifier_server(
    tenant_id: str,
    message: str,
    classifier_url: str,
) -> Optional[ClassifyResult]:
    """Call Rayan's model server POST /classify. Returns None if unavailable."""
    try:
        import httpx

        service_token = get_service_token()
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.post(
                f"{classifier_url.rstrip('/')}/classify",
                headers={"Authorization": f"Bearer {service_token}"},
                json={"tenant_id": tenant_id, "message": message},
            )
            resp.raise_for_status()
            data = resp.json()

        raw_intent = str(data.get("intent", "")).lower()
        raw_route = str(data.get("route", "")).lower()
        intent = normalize_classifier_intent(raw_intent)
        confidence = float(data.get("confidence", 0.0))

        logger.info(
            "CLASSIFIER_RESULT tenant=%s raw_intent=%s raw_route=%s normalized_intent=%s confidence=%.3f",
            tenant_id,
            raw_intent,
            raw_route,
            intent,
            confidence,
        )

        if intent not in INTENTS:
            logger.warning("Classifier server returned unknown intent '%s'", raw_intent)
            return None

        return ClassifyResult(
            intent=intent,
            confidence=confidence,
            source="classifier_server",
            raw_intent=raw_intent,
            raw_route=raw_route,
        )

    except Exception as exc:
        logger.warning("Classifier server unavailable (%s); falling back to LLM", exc)
        return None
