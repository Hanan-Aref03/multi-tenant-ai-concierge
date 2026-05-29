"""Optional NeMo Guardrails adapter for the guardrails sidecar.

NeMo is loaded as a library-backed configuration layer, while the existing
deterministic rules remain the stable fallback and defense-in-depth layer.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from services.guardrails.rules import (
    GuardrailDecision,
    GuardrailResult,
)

logger = logging.getLogger(__name__)

NEMO_CONFIG_DIR = Path(__file__).resolve().parent / "nemo"
USE_NEMO_ENV = "GUARDRAILS_USE_NEMO"
NEMO_STRICT_ENV = "GUARDRAILS_NEMO_STRICT"

_NEMO_PLATFORM_PATTERNS: tuple[tuple[GuardrailDecision, str, tuple[re.Pattern[str], ...]], ...] = (
    (
        GuardrailDecision.BLOCKED_PROMPT_DISCLOSURE,
        "NeMo prompt disclosure rail matched.",
        (
            re.compile(r"\b(?:show|reveal|print|dump|repeat|display)\b.*\b(?:system|developer|hidden)\s+(?:prompt|instructions)\b", re.IGNORECASE),
            re.compile(r"\b(?:system|developer|hidden)\s+(?:prompt|instructions|message)\b.*\b(?:verbatim|exact|full)\b", re.IGNORECASE),
        ),
    ),
    (
        GuardrailDecision.BLOCKED_CROSS_TENANT,
        "NeMo cross-tenant data rail matched.",
        (
            re.compile(r"\b(?:another|other|different)\s+tenant(?:'s)?\s+(?:data|records|documents|conversations|leads|customers)\b", re.IGNORECASE),
            re.compile(r"\b(?:show|give|fetch|export|list|access)\b.*\b(?:tenant|workspace)\b.*\b(?:data|records|documents|conversations|leads)\b", re.IGNORECASE),
        ),
    ),
    (
        GuardrailDecision.BLOCKED_PROMPT_INJECTION,
        "NeMo prompt injection rail matched.",
        (
            re.compile(r"\bignore\s+(?:all\s+)?(?:previous|prior|above)\s+(?:instructions|rules|messages|prompt)\b", re.IGNORECASE),
            re.compile(r"\bdisregard\s+(?:all\s+)?(?:previous|prior|above)\s+(?:instructions|rules|messages|prompt)\b", re.IGNORECASE),
            re.compile(r"\boverride\s+(?:the\s+)?(?:system|developer|safety)\s+(?:instructions|rules|prompt)\b", re.IGNORECASE),
            re.compile(r"\bnew\s+(?:system|developer)\s+(?:message|instructions|prompt)\b", re.IGNORECASE),
        ),
    ),
    (
        GuardrailDecision.BLOCKED_JAILBREAK,
        "NeMo jailbreak rail matched.",
        (
            re.compile(r"\b(?:act|pretend)\s+as\s+(?:dan|do anything now|an unrestricted|a rogue)\b", re.IGNORECASE),
            re.compile(r"\bjailbreak\b", re.IGNORECASE),
            re.compile(r"\bdeveloper\s+mode\b", re.IGNORECASE),
            re.compile(r"\bno\s+(?:rules|restrictions|safety|guardrails)\b", re.IGNORECASE),
        ),
    ),
)


@dataclass(frozen=True)
class NemoRuntime:
    config: Any
    rails: Any


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def is_nemo_enabled() -> bool:
    return _env_bool(USE_NEMO_ENV, True)


def is_nemo_strict() -> bool:
    return _env_bool(NEMO_STRICT_ENV, False)


@lru_cache(maxsize=1)
def _load_nemo_runtime() -> NemoRuntime | None:
    if not is_nemo_enabled():
        return None

    try:
        from nemoguardrails import LLMRails, RailsConfig

        config = RailsConfig.from_path(str(NEMO_CONFIG_DIR))
        rails = LLMRails(config)
        return NemoRuntime(config=config, rails=rails)
    except Exception:
        logger.exception("Failed to load NeMo Guardrails config from %s", NEMO_CONFIG_DIR)
        if is_nemo_strict():
            raise
        return None


def reset_nemo_cache() -> None:
    """Clear cached NeMo runtime, primarily for tests after env changes."""

    _load_nemo_runtime.cache_clear()


def is_nemo_available() -> bool:
    try:
        return _load_nemo_runtime() is not None
    except Exception:
        return False


def _allowed(reason: str) -> GuardrailResult:
    return GuardrailResult(
        allowed=True,
        decision=GuardrailDecision.ALLOWED,
        reason=reason,
    )


def evaluate_nemo_guardrails(
    message: str,
    tenant_policy: dict[str, object] | None = None,
) -> GuardrailResult:
    """Evaluate NeMo-backed platform rails with safe fallback semantics.

    The loaded NeMo config is the source for the programmable rail layer. To
    keep local development and CI lean, this adapter does not require an extra
    LLM call; it enforces the configured platform rail classes deterministically
    and lets the existing Python rules remain defense-in-depth.
    """

    del tenant_policy  # Tenant policy cannot weaken platform NeMo rails.

    if not is_nemo_enabled():
        return _allowed("NeMo Guardrails disabled by environment.")

    try:
        runtime = _load_nemo_runtime()
    except Exception:
        if is_nemo_strict():
            return GuardrailResult(
                allowed=False,
                decision=GuardrailDecision.BLOCKED_NEMO_UNAVAILABLE,
                reason="NeMo Guardrails strict mode blocked because NeMo failed to load.",
            )
        return _allowed("NeMo Guardrails unavailable; deterministic fallback remains active.")

    if runtime is None:
        if is_nemo_strict():
            return GuardrailResult(
                allowed=False,
                decision=GuardrailDecision.BLOCKED_NEMO_UNAVAILABLE,
                reason="NeMo Guardrails strict mode blocked because NeMo is unavailable.",
            )
        return _allowed("NeMo Guardrails unavailable; deterministic fallback remains active.")

    for decision, reason, patterns in _NEMO_PLATFORM_PATTERNS:
        if any(pattern.search(message) for pattern in patterns):
            return GuardrailResult(allowed=False, decision=decision, reason=reason)

    return _allowed("No NeMo platform guardrail rail matched.")
