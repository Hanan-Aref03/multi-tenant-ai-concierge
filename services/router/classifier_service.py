"""Classifier orchestration service."""

import logging
from typing import Dict, List, Optional

from services.router.classifier_client import _call_classifier_server
from services.router.constants import CLASSIFIER_CONFIDENCE_THRESHOLD
from services.router.contracts import ClassifyResult
from services.router.lead_utils import _should_force_lead_capture
from services.router.llm_classifier import _classify_via_llm

logger = logging.getLogger(__name__)


async def classify_intent(
    tenant_id: str,
    message: str,
    conversation_history: List[Dict],
    classifier_url: Optional[str],
    llm_client,
) -> ClassifyResult:
    """
    Classify the intent of *message*.

    Resolution order:
    1. Rayan's model server (if classifier_url is set).
    2. LLM with the intent_classifier prompt (if llm_client is set).
    3. Fallback to knowledge_search with 0.0 confidence -> agent handles it.
    """
    if classifier_url:
        result = await _call_classifier_server(tenant_id, message, classifier_url)
        if result:
            if _should_force_lead_capture(message, result):
                logger.info(
                    "LEAD_KEYWORD_FALLBACK tenant=%s original_intent=%s raw_intent=%s confidence=%.3f",
                    tenant_id,
                    result.intent,
                    result.raw_intent,
                    result.confidence,
                )
                return ClassifyResult(
                    intent="lead_capture",
                    confidence=max(result.confidence, CLASSIFIER_CONFIDENCE_THRESHOLD),
                    source=f"{result.source}:keyword_fallback",
                    raw_intent=result.raw_intent,
                    raw_route=result.raw_route,
                )
            return result

    if llm_client:
        result = await _classify_via_llm(message, conversation_history, llm_client)
        if result:
            if _should_force_lead_capture(message, result):
                logger.info(
                    "LEAD_KEYWORD_FALLBACK tenant=%s original_intent=%s raw_intent=%s confidence=%.3f",
                    tenant_id,
                    result.intent,
                    result.raw_intent,
                    result.confidence,
                )
                return ClassifyResult(
                    intent="lead_capture",
                    confidence=max(result.confidence, CLASSIFIER_CONFIDENCE_THRESHOLD),
                    source=f"{result.source}:keyword_fallback",
                    raw_intent=result.raw_intent,
                    raw_route=result.raw_route,
                )
            return result

    logger.warning("All classifiers failed; defaulting to knowledge_search with 0.0 confidence")
    fallback = ClassifyResult(intent="knowledge_search", confidence=0.0, source="fallback")
    if _should_force_lead_capture(message, fallback):
        return ClassifyResult(
            intent="lead_capture",
            confidence=CLASSIFIER_CONFIDENCE_THRESHOLD,
            source="fallback:keyword_fallback",
        )
    return fallback
