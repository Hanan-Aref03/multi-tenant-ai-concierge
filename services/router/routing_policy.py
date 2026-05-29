"""Routing policy for classified intents."""

from services.router.constants import CLASSIFIER_CONFIDENCE_THRESHOLD
from services.router.contracts import ClassifyResult


def _decide_route(classification: ClassifyResult) -> str:
    """
    Map intent + confidence to a route string.

    Rules (ROUT-01..03):
    - Low confidence -> agent (fallback handles anything uncertain)
    - greeting / off_topic / spam -> direct (no LLM call needed)
    - faq / knowledge_search -> rag
    - lead_capture / escalation -> agent
    """
    if classification.confidence < CLASSIFIER_CONFIDENCE_THRESHOLD:
        return "agent"

    if classification.intent in ("greeting", "off_topic", "spam"):
        return "direct"

    if classification.intent in ("faq", "knowledge_search"):
        return "rag"

    if classification.intent in ("lead_capture", "escalation"):
        return "agent"

    return "agent"
