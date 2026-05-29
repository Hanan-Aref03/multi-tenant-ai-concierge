"""LLM fallback classifier."""

import json
import logging
import os
from typing import Dict, List, Optional

from apps.shared.llm_client import get_chat_model
from services.router.constants import INTENTS
from services.router.contracts import ClassifyResult

logger = logging.getLogger(__name__)


async def _classify_via_llm(
    message: str,
    conversation_history: List[Dict],
    llm_client,
) -> Optional[ClassifyResult]:
    """Classify using the intent_classifier prompt + LLM when the model server is down."""
    try:
        prompt_path = os.path.normpath(
            os.path.join(
                os.path.dirname(__file__),
                "..", "..", "prompts", "router", "intent_classifier.md",
            )
        )
        with open(prompt_path) as f:
            system_prompt = f.read()

        # Include up to 4 recent turns as context so classification is history-aware
        history_context = ""
        if conversation_history:
            recent = conversation_history[-4:]
            history_context = "\n".join(
                f"{m.get('role', 'user').capitalize()}: {m.get('content', '')}"
                for m in recent
            )

        user_content = (
            f"Conversation so far:\n{history_context}\n\nNew message: {message}"
            if history_context
            else message
        )

        response = await llm_client.chat.completions.create(
            model=get_chat_model(),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=0.0,
            max_tokens=64,
        )

        raw = response.choices[0].message.content.strip()
        data = json.loads(raw)
        intent = str(data.get("intent", "")).lower()
        confidence = float(data.get("confidence", 0.0))

        if intent not in INTENTS:
            logger.warning("LLM classifier returned unknown intent '%s'", intent)
            return None

        return ClassifyResult(intent=intent, confidence=confidence, source="llm", raw_intent=intent)

    except Exception as exc:
        logger.error("LLM classification failed: %s", exc)
        return None
