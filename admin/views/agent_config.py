"""AI assistant and safety rule configuration views."""

from __future__ import annotations

import streamlit as st

from api_client import get_agent_config, update_agent_config
from ui import (
    backend_status,
    badge_row,
    empty_state,
    info_card,
    page_header,
    tool_description,
    tool_name,
)

VALID_TOOLS = ["rag_search", "capture_lead", "escalate"]
VALID_TONES = ["polite", "firm", "brief"]


def _fallback_config() -> dict:
    return {
        "agent_persona": "You are a helpful assistant.",
        "enabled_tools": VALID_TOOLS,
        "allowed_topics": [],
        "blocked_topics": [],
        "refusal_tone": "polite",
    }


def _topics_from_text(raw: str) -> list[str]:
    return [topic.strip() for topic in raw.splitlines() if topic.strip()]


def render(mode: str = "agent") -> None:
    data = get_agent_config()
    backend_ready = data is not None
    data = data or _fallback_config()

    if mode == "safety":
        _render_safety(data, backend_ready)
    else:
        _render_agent(data, backend_ready)


def _render_agent(data: dict, backend_ready: bool) -> None:
    page_header(
        "AI Agent",
        "Tune how your website assistant sounds and what it can do for visitors.",
        "Assistant",
    )
    backend_status(backend_ready)

    left, right = st.columns([1.08, 0.92], gap="large")
    with left:
        with st.form("agent_form"):
            st.subheader("Assistant Personality")
            persona = st.text_area(
                "Personality and tone",
                value=data.get("agent_persona", ""),
                height=170,
                placeholder="Example: Be warm, concise, and helpful. Answer like a knowledgeable front desk assistant.",
                help="This controls the assistant's voice in the visitor chat.",
            )

            st.subheader("What the Assistant Can Do")
            current_tools = [tool for tool in data.get("enabled_tools", VALID_TOOLS) if tool in VALID_TOOLS]
            selected_labels = st.multiselect(
                "Capabilities",
                options=[tool_name(tool) for tool in VALID_TOOLS],
                default=[tool_name(tool) for tool in current_tools],
                help="Choose the actions available in visitor conversations.",
            )
            label_to_id = {tool_name(tool): tool for tool in VALID_TOOLS}
            enabled_tools = [label_to_id[label] for label in selected_labels]

            st.subheader("When to Ask for Human Help")
            st.caption("Use handoff when a request needs a person, special approval, or follow-up.")

            saved = st.form_submit_button("Save AI agent", use_container_width=True)

        if saved:
            if backend_ready:
                result = update_agent_config(
                    persona,
                    enabled_tools,
                    data.get("allowed_topics", []),
                    data.get("blocked_topics", []),
                    data.get("refusal_tone", "polite"),
                )
                if result:
                    st.success("AI agent updated.")
                    st.rerun()
            else:
                st.error("Connect the admin API before saving changes.")

    with right:
        st.subheader("Assistant Preview")
        intro = data.get("agent_persona", "You are a helpful assistant.")
        st.markdown(
            f"""
            <div class="c-section">
                <div class="c-label">Visitor chat</div>
                <div class="c-value">Hi, I am your concierge.</div>
                <div class="c-help">{intro[:220]}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.subheader("Enabled Today")
        if data.get("enabled_tools"):
            for tool in data.get("enabled_tools", []):
                info_card(tool_name(tool), tool_description(tool), "soft")
        else:
            empty_state("No capabilities selected", "Pick at least one assistant capability.")


def _render_safety(data: dict, backend_ready: bool) -> None:
    page_header(
        "Safety Rules",
        "Keep the assistant helpful, on-brand, and safe for your business.",
        "Safety",
    )
    backend_status(backend_ready)
    badge_row([("Required protections on", "success"), ("Business rules editable", "locked")])

    left, right = st.columns([0.92, 1.08], gap="large")
    with left:
        st.subheader("Required Safety Protections")
        badge_row([("Locked", "locked")])
        info_card("Prompt attack protection", "Blocks attempts to override assistant instructions.", "soft")
        info_card("Cross-business data protection", "Keeps business workspaces separated.", "soft")
        info_card("Sensitive info protection", "Reduces exposure of private or unsafe content.", "soft")

    with right:
        st.subheader("Business Rules")
        with st.form("safety_form"):
            allowed_topics_text = st.text_area(
                "Allowed topics",
                value="\n".join(data.get("allowed_topics", [])),
                height=105,
                placeholder="Product questions\nPricing\nBooking support",
                help="Optional. Leave blank if your assistant can answer broadly from your content.",
            )
            blocked_topics_text = st.text_area(
                "Blocked topics",
                value="\n".join(data.get("blocked_topics", [])),
                height=105,
                placeholder="Legal advice\nMedical advice\nCompetitor details",
                help="Topics the assistant should avoid or redirect.",
            )
            refusal_tone = st.selectbox(
                "Refusal tone",
                options=VALID_TONES,
                format_func=lambda tone: tone.title(),
                index=VALID_TONES.index(data.get("refusal_tone", "polite"))
                if data.get("refusal_tone", "polite") in VALID_TONES
                else 0,
            )
            saved = st.form_submit_button("Save safety rules", use_container_width=True)

        if saved:
            if backend_ready:
                result = update_agent_config(
                    data.get("agent_persona", ""),
                    data.get("enabled_tools", VALID_TOOLS),
                    _topics_from_text(allowed_topics_text),
                    _topics_from_text(blocked_topics_text),
                    refusal_tone,
                )
                if result:
                    st.success("Safety rules updated.")
                    st.rerun()
            else:
                st.error("Connect the admin API before saving changes.")
