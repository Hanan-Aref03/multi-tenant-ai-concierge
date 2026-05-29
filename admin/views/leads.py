"""Lead inbox view."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from api_client import get_leads
from ui import backend_status, badge_row, empty_state, metric_card, page_header

PAGE_SIZE = 50


def render() -> None:
    page_header(
        "Leads",
        "Follow up with people who shared contact details through your website widget.",
        "Mini CRM",
    )

    if "leads_offset" not in st.session_state:
        st.session_state["leads_offset"] = 0

    data = get_leads(limit=PAGE_SIZE, offset=st.session_state["leads_offset"])
    backend_ready = data is not None
    data = data or {"total": 0, "leads": []}

    backend_status(backend_ready)
    badge_row([("Visitor leads", "success"), "Contact details", "Follow-up intent"])

    total = data.get("total", 0)
    leads = data.get("leads", [])
    current_page = (st.session_state["leads_offset"] // PAGE_SIZE) + 1
    max_page = max(1, ((total - 1) // PAGE_SIZE) + 1) if total else 1

    col1, col2, col3 = st.columns(3)
    with col1:
        metric_card("Total Leads", total, "All captured contacts.", "success")
    with col2:
        metric_card("Current Page", f"{current_page} of {max_page}", "Lead inbox pagination.")
    with col3:
        metric_card("Inbox Status", "Ready", "New leads appear here.", "blue")

    if leads:
        query = st.text_input("Search leads", placeholder="Search by name, contact, or intent")
        df = pd.DataFrame(leads)
        visible_columns = [col for col in ["captured_at", "visitor_name", "contact", "intent"] if col in df.columns]
        df = df[visible_columns]
        if query:
            searchable = df.astype(str).agg(" ".join, axis=1).str.lower()
            df = df[searchable.str.contains(query.lower(), na=False)]
        df = df.rename(
            columns={
                "captured_at": "Date",
                "visitor_name": "Name",
                "contact": "Contact",
                "intent": "Intent",
            }
        )
        if "Status" not in df.columns:
            df["Status"] = "New"
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        empty_state(
            "No leads yet",
            "When visitors share contact details through the widget, they will appear here.",
        )

    col1, _, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("Previous", disabled=st.session_state["leads_offset"] <= 0, use_container_width=True):
            st.session_state["leads_offset"] -= PAGE_SIZE
            st.rerun()
    with col3:
        has_next = (st.session_state["leads_offset"] + PAGE_SIZE) < total
        if st.button("Next", disabled=not has_next, use_container_width=True):
            st.session_state["leads_offset"] += PAGE_SIZE
            st.rerun()
