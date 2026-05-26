"""Typed API client for Streamlit admin - wraps FastAPI admin endpoints."""

from __future__ import annotations

import os
from typing import Any

import requests
import streamlit as st

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
API_TIMEOUT_SECONDS = float(os.getenv("API_TIMEOUT_SECONDS", "5"))


def _headers() -> dict:
    token = st.session_state.get("token", "")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _handle(res: requests.Response) -> Any:
    if res.status_code == 401:
        st.session_state.clear()
        st.error("Session expired - please sign in again")
        st.stop()
    if res.status_code == 403:
        st.error("Access denied")
        return None
    if not res.ok:
        st.error(f"API error {res.status_code}: {res.text}")
        return None
    return res.json()


def _request(method: str, path: str, **kwargs) -> Any:
    try:
        response = requests.request(
            method,
            f"{API_BASE}{path}",
            headers=_headers(),
            timeout=API_TIMEOUT_SECONDS,
            **kwargs,
        )
    except requests.RequestException:
        return None
    return _handle(response)


def get_widget_config() -> dict | None:
    return _request("get", "/api/admin/widget")


def update_widget_config(greeting: str, accent_colour: str, allowed_origins: list[str]) -> dict | None:
    return _request(
        "put",
        "/api/admin/widget",
        json={"greeting": greeting, "accent_colour": accent_colour, "allowed_origins": allowed_origins},
    )


def get_agent_config() -> dict | None:
    return _request("get", "/api/admin/config")


def update_agent_config(
    agent_persona: str,
    enabled_tools: list[str],
    allowed_topics: list[str],
    blocked_topics: list[str],
    refusal_tone: str,
) -> dict | None:
    return _request(
        "put",
        "/api/admin/config",
        json={
            "agent_persona": agent_persona,
            "enabled_tools": enabled_tools,
            "allowed_topics": allowed_topics,
            "blocked_topics": blocked_topics,
            "refusal_tone": refusal_tone,
        },
    )


def get_leads(limit: int = 50, offset: int = 0) -> dict | None:
    return _request("get", "/api/admin/leads", params={"limit": limit, "offset": offset})
