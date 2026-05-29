"""Lead-capture detection and contact extraction helpers."""

import re
from typing import Dict, Optional

from services.router.constants import (
    CLASSIFIER_CONFIDENCE_THRESHOLD,
    EMAIL_RE,
    NAME_RE,
    PHONE_RE,
    SALES_KEYWORDS,
)
from services.router.contracts import ClassifyResult


def _has_sales_signal(message: str) -> bool:
    lowered = message.lower()
    return any(keyword in lowered for keyword in SALES_KEYWORDS)


def _extract_contact(message: str) -> Dict[str, Optional[str]]:
    email_match = EMAIL_RE.search(message)
    phone_match = PHONE_RE.search(message)
    name_match = NAME_RE.search(message)
    name = None
    if name_match:
        name = re.split(
            r"\s+(?:and|email|phone|at|contact)\b",
            name_match.group(1).strip(" .,!?:;"),
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0].strip(" .,!?:;")
    return {
        "name": name,
        "email": email_match.group(0) if email_match else None,
        "phone": phone_match.group(0).strip() if phone_match else None,
    }


def _has_contact_info(message: str) -> bool:
    contact = _extract_contact(message)
    return bool(contact["email"] or contact["phone"])


def _should_force_lead_capture(message: str, classification: ClassifyResult) -> bool:
    if classification.intent == "lead_capture":
        return True
    if not _has_sales_signal(message):
        return False
    return (
        classification.intent in {"knowledge_search", "faq", "escalation"}
        or classification.confidence < CLASSIFIER_CONFIDENCE_THRESHOLD
    )
