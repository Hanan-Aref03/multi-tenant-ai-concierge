"""Widget customization and install views."""

from __future__ import annotations

import streamlit as st

from api_client import get_widget_config, update_widget_config
from ui import BUSINESS_NAME, backend_status, badge_row, empty_state, metric_card, page_header, widget_preview


def _fallback_widget() -> dict:
    return {
        "widget_id": "tenant-widget",
        "greeting": "Hi! How can I help you?",
        "accent_colour": "#3B82F6",
        "allowed_origins": ["http://localhost:3000", "http://localhost:5173"],
        "embed_snippet": (
            '<script src="http://localhost:8000/widget.js" '
            'data-widget-id="YOUR_WIDGET_ID" '
            'data-api-base="http://localhost:8000"></script>'
        ),
    }


def render(mode: str = "config") -> None:
    data = get_widget_config()
    backend_ready = data is not None
    data = data or _fallback_widget()

    if mode == "install":
        _render_install(data, backend_ready)
    else:
        _render_config(data, backend_ready)


def _render_config(data: dict, backend_ready: bool) -> None:
    page_header(
        "Widget",
        "Customize the chat widget visitors will see on your website.",
        "Visitor Experience",
    )
    backend_status(backend_ready)

    col1, col2, col3 = st.columns(3)
    with col1:
        metric_card("Widget Status", "Ready", "Configured for visitor chat.", "success")
    with col2:
        metric_card("Widget ID", data.get("widget_id", "Not available"), "Used by your install script.", "blue")
    with col3:
        metric_card("Allowed Websites", len(data.get("allowed_origins", [])), "Where the widget can appear.")

    left, right = st.columns([1.05, 0.95], gap="large")
    with left:
        with st.form("widget_form"):
            st.subheader("Branding")
            greeting = st.text_input(
                "Greeting message",
                value=data.get("greeting", ""),
                placeholder="Hi! How can I help you?",
                help="The first message visitors see when the chat opens.",
            )
            accent_colour = st.color_picker(
                "Brand color",
                value=data.get("accent_colour", "#3B82F6"),
                help="Used for the widget header and highlights.",
            )

            st.subheader("Allowed Websites")
            origins_text = st.text_area(
                "Website domains",
                value="\n".join(data.get("allowed_origins", [])),
                height=120,
                placeholder="https://example.com\nhttps://www.example.com",
                help="Enter one website origin per line.",
            )

            saved = st.form_submit_button("Save widget", use_container_width=True)

        if saved:
            if backend_ready:
                origins = [origin.strip() for origin in origins_text.splitlines() if origin.strip()]
                result = update_widget_config(greeting, accent_colour, origins)
                if result:
                    st.success("Widget updated.")
                    st.rerun()
            else:
                st.error("Connect the admin API before saving changes.")

    with right:
        st.subheader("Live Preview")
        widget_preview(data.get("greeting", ""), data.get("accent_colour", "#3B82F6"), BUSINESS_NAME)


def _render_install(data: dict, backend_ready: bool) -> None:
    page_header(
        "Install Widget",
        "Paste this script before the closing body tag on your website.",
        "Website Install",
    )
    backend_status(backend_ready)

    snippet = data.get("embed_snippet", "")
    if not snippet:
        empty_state("Script not ready", "Save your widget settings first, then return here to install it.")
        return

    left, right = st.columns([1.2, 0.8], gap="large")
    with left:
        st.subheader("Install Script")
        st.code(snippet, language="html")
        st.download_button(
            "Download script",
            data=snippet,
            file_name="concierge-widget-snippet.html",
            mime="text/html",
            use_container_width=True,
        )

    with right:
        st.subheader("Install Checklist")
        domains_ready = bool(data.get("allowed_origins"))
        checklist = [
            ("Website domain approved", domains_ready),
            ("Widget configured", bool(data.get("greeting"))),
            ("Script ready", bool(snippet)),
            ("Secure chat enabled", True),
        ]
        for label, ready in checklist:
            badge_row([(label, "success" if ready else "warning")])
        st.caption("Security note: the existing widget token flow is unchanged.")
