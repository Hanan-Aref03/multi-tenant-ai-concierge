"""Agent Config admin page — persona, tools, guardrail rules."""
import streamlit as st

from api_client import get_agent_config, update_agent_config

VALID_TOOLS = ["rag_search", "capture_lead", "escalate"]
VALID_TONES = ["polite", "firm", "brief"]

st.title("Agent Configuration")
st.caption("Configure the AI agent's persona and behaviour for your widget.")

data = get_agent_config()
if data is None:
    st.stop()

with st.form("agent_form"):
    st.subheader("Persona")
    persona = st.text_area(
        "Agent persona (system prompt prefix)",
        value=data.get("agent_persona", ""),
        height=150,
        help="This text is injected at the start of every conversation as the agent's identity.",
    )

    st.subheader("Enabled Tools")
    enabled_tools = []
    for tool in VALID_TOOLS:
        if st.checkbox(tool, value=tool in data.get("enabled_tools", VALID_TOOLS)):
            enabled_tools.append(tool)

    st.subheader("Guardrail Rules")
    st.caption("Platform rails (injection, jailbreak, cross-tenant) are always enforced. You can only tune business-level rules.")
    allowed_topics_text = st.text_area(
        "Allowed topics (one per line)",
        value="\n".join(data.get("allowed_topics", [])),
        height=80,
    )
    blocked_topics_text = st.text_area(
        "Blocked topics (one per line)",
        value="\n".join(data.get("blocked_topics", [])),
        height=80,
    )
    refusal_tone = st.selectbox(
        "Refusal tone",
        options=VALID_TONES,
        index=VALID_TONES.index(data.get("refusal_tone", "polite")),
    )

    saved = st.form_submit_button("Save changes")

if saved:
    allowed_topics = [t.strip() for t in allowed_topics_text.splitlines() if t.strip()]
    blocked_topics = [t.strip() for t in blocked_topics_text.splitlines() if t.strip()]
    result = update_agent_config(persona, enabled_tools, allowed_topics, blocked_topics, refusal_tone)
    if result:
        st.success("Agent config saved.")
        st.rerun()
