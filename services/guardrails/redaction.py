"""PII and secret redaction helpers.

Rayan owns the redaction logic before logs, traces, or memory persistence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(
    r"(?<!\w)(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]?\d{4}(?!\w)"
)
API_KEY_RE = re.compile(
    r"\b(?:sk-[A-Za-z0-9_-]{8,}|gsk_[A-Za-z0-9_-]{8,}|xoxb-[A-Za-z0-9-]{8,}|ghp_[A-Za-z0-9_]{8,})\b"
)
AUTH_TOKEN_RE = re.compile(
    r"\b(?:authorization|bearer token|access token|api token)\s*[:=]\s*(?:Bearer\s+)?[A-Za-z0-9._~+/=-]{8,}",
    re.IGNORECASE,
)
BEARER_RE = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE)


@dataclass(frozen=True)
class RedactionResult:
    text: str
    redactions: tuple[str, ...]


def redact_text(text: str) -> RedactionResult:
    """Redact common PII and secrets from free-form text."""

    redactions: list[str] = []
    redacted = text

    for label, pattern, replacement in (
        ("authorization_token", AUTH_TOKEN_RE, "[REDACTED_AUTH_TOKEN]"),
        ("bearer_token", BEARER_RE, "Bearer [REDACTED_BEARER_TOKEN]"),
        ("api_key", API_KEY_RE, "[REDACTED_API_KEY]"),
        ("email", EMAIL_RE, "[REDACTED_EMAIL]"),
        ("phone", PHONE_RE, "[REDACTED_PHONE]"),
    ):
        redacted, count = pattern.subn(replacement, redacted)
        if count:
            redactions.append(label)

    return RedactionResult(text=redacted, redactions=tuple(redactions))


def redact(text: str) -> str:
    """Return only redacted text for callers that do not need metadata."""

    return redact_text(text).text
