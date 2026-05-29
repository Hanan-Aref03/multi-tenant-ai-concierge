"""Reusable Streamlit UI helpers for the Concierge admin."""

from __future__ import annotations

from html import escape
from typing import Iterable

import streamlit as st


BUSINESS_NAME = "Demo Business"
CURRENT_PLAN = "Demo mode"


TOOL_LABELS = {
    "rag_search": ("Answer from content", "Use approved business content to answer visitor questions."),
    "capture_lead": ("Capture contact details", "Collect visitor contact info when they want follow-up."),
    "escalate": ("Hand off to human", "Route conversations that need a person."),
}


def apply_theme() -> None:
    """Apply a focused product-dashboard polish layer."""
    st.markdown(
        """
        <style>
        :root {
            --c-border: #E5E7EB;
            --c-muted: #64748B;
            --c-soft: #F8FAFC;
            --c-ink: #0F172A;
            --c-blue: #2563EB;
            --c-green: #047857;
            --c-amber: #B45309;
            --c-red: #B91C1C;
        }
        .block-container {
            padding-top: 1.25rem;
            padding-bottom: 2.5rem;
            max-width: 1220px;
        }
        [data-testid="stSidebar"] {
            background: #0F172A;
        }
        [data-testid="stSidebarNav"] {
            display: none;
        }
        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3,
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] span {
            color: #E5E7EB;
        }
        [data-testid="stSidebar"] .stButton > button {
            border-color: rgba(255, 255, 255, 0.16);
            background: rgba(255, 255, 255, 0.06);
            color: #F8FAFC;
        }
        div[role="radiogroup"] label {
            border-radius: 8px;
            padding: .28rem .35rem;
        }
        .c-kicker {
            color: var(--c-blue);
            font-size: .76rem;
            font-weight: 750;
            letter-spacing: .05em;
            text-transform: uppercase;
            margin-bottom: .2rem;
        }
        .c-title {
            color: var(--c-ink);
            font-size: 2rem;
            font-weight: 760;
            line-height: 1.15;
            margin: 0 0 .25rem 0;
        }
        .c-copy {
            color: var(--c-muted);
            font-size: 1rem;
            line-height: 1.5;
            margin: 0 0 1rem 0;
            max-width: 820px;
        }
        .c-card {
            border: 1px solid var(--c-border);
            border-radius: 8px;
            background: #FFFFFF;
            padding: 1rem;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
            min-height: 108px;
        }
        .c-card.soft {
            background: var(--c-soft);
        }
        .c-label {
            color: var(--c-muted);
            font-size: .75rem;
            font-weight: 750;
            letter-spacing: .03em;
            text-transform: uppercase;
            margin-bottom: .35rem;
        }
        .c-value {
            color: var(--c-ink);
            font-size: 1.3rem;
            font-weight: 760;
            line-height: 1.25;
            margin-bottom: .35rem;
            overflow-wrap: anywhere;
        }
        .c-help {
            color: var(--c-muted);
            font-size: .88rem;
            line-height: 1.4;
        }
        .c-badges {
            display: flex;
            flex-wrap: wrap;
            gap: .45rem;
            margin: .15rem 0 1rem 0;
        }
        .c-badge {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            border: 1px solid var(--c-border);
            background: #FFFFFF;
            color: #334155;
            font-size: .78rem;
            font-weight: 700;
            line-height: 1;
            padding: .42rem .62rem;
            white-space: nowrap;
        }
        .c-badge.success {
            border-color: #A7F3D0;
            background: #ECFDF5;
            color: var(--c-green);
        }
        .c-badge.warning {
            border-color: #FDE68A;
            background: #FFFBEB;
            color: var(--c-amber);
        }
        .c-badge.locked {
            border-color: #BFDBFE;
            background: #EFF6FF;
            color: #1D4ED8;
        }
        .c-section {
            border: 1px solid var(--c-border);
            border-radius: 8px;
            background: #FFFFFF;
            padding: 1rem;
            margin: .65rem 0 1rem 0;
        }
        .c-empty {
            border: 1px dashed #CBD5E1;
            border-radius: 8px;
            background: #F8FAFC;
            padding: 1.2rem;
            color: #475569;
        }
        .c-empty strong {
            color: #0F172A;
            font-size: 1rem;
        }
        .c-widget {
            width: 100%;
            max-width: 360px;
            margin-left: auto;
            border: 1px solid #CBD5E1;
            border-radius: 16px;
            background: #FFFFFF;
            box-shadow: 0 20px 45px rgba(15, 23, 42, .12);
            overflow: hidden;
        }
        .c-widget-head {
            color: #FFFFFF;
            padding: .85rem 1rem;
            font-weight: 750;
        }
        .c-widget-body {
            background: #F8FAFC;
            padding: 1rem;
        }
        .c-bubble {
            background: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 14px;
            padding: .75rem;
            color: #334155;
            font-size: .92rem;
            line-height: 1.4;
        }
        .c-mini-list {
            margin: .55rem 0 0 0;
            padding-left: 1.1rem;
            color: #475569;
        }
        .c-mini-list li {
            margin: .18rem 0;
        }
        textarea, input, .stSelectbox {
            font-size: .95rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_header(title: str, description: str = "", kicker: str = "Concierge") -> None:
    copy = f'<div class="c-copy">{escape(description)}</div>' if description else ""
    st.markdown(
        f"""
        <div class="c-kicker">{escape(kicker)}</div>
        <h1 class="c-title">{escape(title)}</h1>
        {copy}
        """,
        unsafe_allow_html=True,
    )


def badge(label: str, tone: str = "") -> str:
    css_class = f"c-badge {tone}".strip()
    return f'<span class="{css_class}">{escape(label)}</span>'


def badge_row(labels: Iterable[tuple[str, str] | str]) -> None:
    rendered = []
    for item in labels:
        if isinstance(item, tuple):
            rendered.append(badge(item[0], item[1]))
        else:
            rendered.append(badge(item))
    st.markdown(f'<div class="c-badges">{"".join(rendered)}</div>', unsafe_allow_html=True)


def metric_card(label: str, value: str | int, help_text: str = "", tone: str | None = None) -> None:
    tone_style = ""
    if tone == "success":
        tone_style = "border-top: 3px solid #10B981;"
    elif tone == "warning":
        tone_style = "border-top: 3px solid #F59E0B;"
    elif tone == "blue":
        tone_style = "border-top: 3px solid #2563EB;"
    elif tone == "muted":
        tone_style = "opacity: .72;"
    help_html = f'<div class="c-help">{escape(help_text)}</div>' if help_text else ""
    st.markdown(
        f"""
        <div class="c-card" style="{tone_style}">
            <div class="c-label">{escape(label)}</div>
            <div class="c-value">{escape(str(value))}</div>
            {help_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def info_card(title: str, body: str, tone: str = "") -> None:
    tone_class = "soft" if tone == "soft" else ""
    st.markdown(
        f"""
        <div class="c-card {tone_class}">
            <div class="c-value">{escape(title)}</div>
            <div class="c-help">{escape(body)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def empty_state(title: str, body: str) -> None:
    st.markdown(
        f"""
        <div class="c-empty">
            <strong>{escape(title)}</strong><br>
            {escape(body)}
        </div>
        """,
        unsafe_allow_html=True,
    )


def backend_status(ready: bool) -> None:
    if ready:
        badge_row([("Connected", "success"), ("Admin access", "locked")])
    else:
        badge_row([("Demo preview", "warning"), ("Changes paused", "warning")])
        st.info("Live settings are not connected right now. You can still preview the admin experience.")


def tool_name(tool_id: str) -> str:
    return TOOL_LABELS.get(tool_id, (tool_id.replace("_", " ").title(), ""))[0]


def tool_description(tool_id: str) -> str:
    return TOOL_LABELS.get(tool_id, ("", ""))[1]


def widget_preview(greeting: str, accent_colour: str, business_name: str = BUSINESS_NAME) -> None:
    safe_colour = accent_colour if isinstance(accent_colour, str) and accent_colour.startswith("#") else "#2563EB"
    st.markdown(
        f"""
        <div class="c-widget">
            <div class="c-widget-head" style="background:{escape(safe_colour)};">
                {escape(business_name)} Concierge
            </div>
            <div class="c-widget-body">
                <div class="c-bubble">{escape(greeting or "Hi! How can I help you?")}</div>
                <ul class="c-mini-list">
                    <li>Answers visitor questions</li>
                    <li>Captures interested leads</li>
                    <li>Hands off when needed</li>
                </ul>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
