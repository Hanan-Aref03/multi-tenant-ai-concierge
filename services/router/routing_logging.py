"""Routing decision logging."""

import hashlib
import logging

from services.router.contracts import ClassifyResult

logger = logging.getLogger("services.router.router")


def _log_routing(
    tenant_id: str,
    session_id: str,
    message: str,
    classification: ClassifyResult,
    routed_to: str,
) -> None:
    message_hash = hashlib.sha256(message.encode()).hexdigest()[:16]
    logger.info(
        "ROUTING_DECISION tenant=%s session=%s msg_hash=%s intent=%s "
        "confidence=%.3f routed_to=%s classifier_source=%s raw_intent=%s raw_route=%s",
        tenant_id,
        session_id,
        message_hash,
        classification.intent,
        classification.confidence,
        routed_to,
        classification.source,
        classification.raw_intent,
        classification.raw_route,
    )
