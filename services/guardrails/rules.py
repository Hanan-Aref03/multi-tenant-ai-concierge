"""Deterministic platform guardrail rules."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class GuardrailDecision(StrEnum):
    ALLOWED = "allowed"
    BLOCKED_PROMPT_INJECTION = "blocked_prompt_injection"
    BLOCKED_JAILBREAK = "blocked_jailbreak"
    BLOCKED_PROMPT_DISCLOSURE = "blocked_prompt_disclosure"
    BLOCKED_CROSS_TENANT = "blocked_cross_tenant"


@dataclass(frozen=True)
class GuardrailResult:
    allowed: bool
    decision: GuardrailDecision
    reason: str


Rule = tuple[GuardrailDecision, str, tuple[re.Pattern[str], ...]]


RULES: tuple[Rule, ...] = (
    (
        GuardrailDecision.BLOCKED_PROMPT_DISCLOSURE,
        "Requests to reveal system or developer instructions are blocked.",
        (
            re.compile(r"\b(?:show|reveal|print|dump|repeat|display)\b.*\b(?:system|developer)\s+prompt\b", re.IGNORECASE),
            re.compile(r"\b(?:system|developer)\s+(?:prompt|instructions|message)\b.*\b(?:verbatim|exact|full)\b", re.IGNORECASE),
        ),
    ),
    (
        GuardrailDecision.BLOCKED_CROSS_TENANT,
        "Requests for another tenant's data are blocked.",
        (
            re.compile(r"\b(?:another|other|different)\s+tenant(?:'s)?\s+(?:data|records|documents|conversations|leads|customers)\b", re.IGNORECASE),
            re.compile(r"\btenant\s+[a-z0-9_-]+\b.*\b(?:tenant\s+[a-z0-9_-]+|data|records|documents|conversations|leads)\b", re.IGNORECASE),
            re.compile(r"\b(?:show|give|fetch|export|list|access)\b.*\b(?:tenant|customer|workspace)\b.*\b(?:data|records|documents|conversations|leads)\b", re.IGNORECASE),
        ),
    ),
    (
        GuardrailDecision.BLOCKED_PROMPT_INJECTION,
        "Prompt injection attempts are blocked.",
        (
            re.compile(r"\bignore\s+(?:all\s+)?(?:previous|prior|above)\s+(?:instructions|rules|messages|prompt)\b", re.IGNORECASE),
            re.compile(r"\bdisregard\s+(?:all\s+)?(?:previous|prior|above)\s+(?:instructions|rules|messages|prompt)\b", re.IGNORECASE),
            re.compile(r"\boverride\s+(?:the\s+)?(?:system|developer|safety)\s+(?:instructions|rules|prompt)\b", re.IGNORECASE),
            re.compile(r"\bnew\s+(?:system|developer)\s+(?:message|instructions|prompt)\b", re.IGNORECASE),
        ),
    ),
    (
        GuardrailDecision.BLOCKED_JAILBREAK,
        "Jailbreak attempts are blocked.",
        (
            re.compile(r"\b(?:act|pretend)\s+as\s+(?:dan|do anything now|an unrestricted|a rogue)\b", re.IGNORECASE),
            re.compile(r"\bjailbreak\b", re.IGNORECASE),
            re.compile(r"\bdeveloper\s+mode\b", re.IGNORECASE),
            re.compile(r"\bno\s+(?:rules|restrictions|safety|guardrails)\b", re.IGNORECASE),
        ),
    ),
)


def evaluate_platform_rules(message: str) -> GuardrailResult:
    """Return the first matching immutable platform guardrail decision."""

    for decision, reason, patterns in RULES:
        if any(pattern.search(message) for pattern in patterns):
            return GuardrailResult(allowed=False, decision=decision, reason=reason)

    return GuardrailResult(
        allowed=True,
        decision=GuardrailDecision.ALLOWED,
        reason="No platform guardrail rule matched.",
    )
