"""Shared helpers for building the chat/completions client.

The project prefers Gemini when a Gemini API key is present, and otherwise
falls back to OpenAI-compatible configuration. The returned client intentionally
keeps the OpenAI chat-completions interface so the rest of the codebase does
not need provider-specific branches.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

GEMINI_OPENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
DEFAULT_OPENAI_CHAT_MODEL = "gpt-4.1-mini"
DEFAULT_GEMINI_CHAT_MODEL = "gemini-2.0-flash"


def _first_env(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def get_llm_provider() -> str:
    """Return the configured provider name.

    Preference order:
    1. Explicit CHAT_PROVIDER override.
    2. Gemini if a Gemini / Google key exists.
    3. OpenAI if an OpenAI key exists.
    4. "none" if nothing is configured.
    """

    explicit = os.getenv("CHAT_PROVIDER", "").strip().lower()
    if explicit in {"gemini", "openai"}:
        return explicit

    if _first_env("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        return "gemini"

    if _first_env("OPENAI_API_KEY"):
        return "openai"

    return "none"


def get_chat_model() -> str:
    """Return the chat model name for the active provider."""

    provider = get_llm_provider()

    if provider == "gemini":
        return os.getenv("GEMINI_CHAT_MODEL", DEFAULT_GEMINI_CHAT_MODEL)
    if provider == "openai":
        return os.getenv("OPENAI_CHAT_MODEL", os.getenv("CHAT_MODEL", DEFAULT_OPENAI_CHAT_MODEL))
    return os.getenv("CHAT_MODEL", DEFAULT_OPENAI_CHAT_MODEL)


def build_llm_client() -> Optional[object]:
    """Build an OpenAI-compatible async client for the configured provider."""

    try:
        import openai  # type: ignore[import]
    except Exception as exc:  # pragma: no cover - only hits when dependency missing
        logger.warning("OpenAI SDK unavailable: %s", exc)
        return None

    provider = get_llm_provider()

    if provider == "gemini":
        api_key = _first_env("GEMINI_API_KEY", "GOOGLE_API_KEY")
        if not api_key:
            logger.warning("Gemini provider selected but no Gemini key is configured")
            return None
        return openai.AsyncOpenAI(api_key=api_key, base_url=GEMINI_OPENAI_BASE_URL)

    if provider == "openai":
        api_key = _first_env("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OpenAI provider selected but OPENAI_API_KEY is empty")
            return None
        return openai.AsyncOpenAI(api_key=api_key)

    logger.warning("No LLM provider configured; LLM client disabled")
    return None
