"""Leads page - read-only table of captured visitor leads for this tenant."""

import pandas as pd
import streamlit as st

from api_client import get_leads

st.title("Captured Leads")
st.caption("All leads captured by the agent for your tenant. Read-only.")

PAGE_SIZE = 50

if "leads_offset" not in st.session_state:
    st.session_state["leads_offset"] = 0

data = get_leads(limit=PAGE_SIZE, offset=st.session_state["leads_offset"])
backend_ready = data is not None
if not backend_ready:
    st.warning(
        "The admin API is not reachable yet, so this page is showing an empty lead table. "
        "Once the backend is up, captured leads will appear here."
    )
    data = {"total": 0, "leads": []}

total = data.get("total", 0)
leads = data.get("leads", [])

st.metric("Total leads", total)

if leads:
    df = pd.DataFrame(leads)[["captured_at", "visitor_name", "contact", "intent"]]
    df.columns = ["Captured At", "Name", "Contact", "Intent"]
    st.dataframe(df, use_container_width=True)
else:
    st.info("No leads captured yet.")

col1, col2, col3 = st.columns([1, 2, 1])
with col1:
    if st.button("<- Previous") and st.session_state["leads_offset"] > 0:
        st.session_state["leads_offset"] -= PAGE_SIZE
        st.rerun()
with col3:
    if st.button("Next ->") and (st.session_state["leads_offset"] + PAGE_SIZE) < total:
        st.session_state["leads_offset"] += PAGE_SIZE
        st.rerun()
