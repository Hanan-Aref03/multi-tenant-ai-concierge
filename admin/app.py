"""Concierge Tenant Admin - Streamlit app entry point."""

from __future__ import annotations

import streamlit as st

from api_client import get_agent_config, get_leads, get_widget_config
from ui import (
    BUSINESS_NAME,
    CURRENT_PLAN,
    apply_theme,
    backend_status,
    badge_row,
    empty_state,
    info_card,
    metric_card,
    page_header,
    tool_name,
)

st.set_page_config(page_title="Concierge Admin", layout="wide")
apply_theme()

NAV_ITEMS = [
    "Dashboard",
    "Business Profile",
    "Content",
    "AI Agent",
    "Safety Rules",
    "Widget",
    "Install Widget",
    "Leads",
    "Analytics",
]

if "token" not in st.session_state:
    st.session_state["token"] = None
if "page" not in st.session_state:
    st.session_state["page"] = "Dashboard"


def login_form() -> None:
    left, right = st.columns([1.05, 0.95], gap="large")
    with left:
        page_header(
            "Concierge Admin",
            "Manage your AI website assistant, brand the widget, and follow up with new leads.",
            "Business Dashboard",
        )
        badge_row([("Demo ready", "success"), "AI concierge", "Lead capture"])
        info_card(
            "Your visitor experience starts here",
            "Configure what visitors see in the chat widget, how the assistant behaves, and where captured leads appear.",
            "soft",
        )
    with right:
        st.subheader("Sign in")
        st.caption("Use your tenant admin credentials.")
        with st.form("login"):
            email = st.text_input("Email", placeholder="admin@business.com")
            password = st.text_input("Password", type="password", placeholder="Password")
            submitted = st.form_submit_button("Sign in", use_container_width=True)
        if submitted:
            # Existing demo login stub. Backend auth wiring is unchanged.
            if email and password:
                st.session_state["token"] = "stub-token"
                st.session_state["email"] = email
                st.rerun()
            else:
                st.error("Enter email and password.")


def _quick_action(label: str, destination: str) -> None:
    if st.button(label, use_container_width=True):
        st.session_state["page"] = destination
        st.rerun()


def render_dashboard() -> None:
    page_header(
        "Welcome back",
        "Here is how your AI concierge is set up for visitors right now.",
        "Dashboard",
    )

    widget = get_widget_config()
    agent = get_agent_config()
    leads = get_leads(limit=5, offset=0)
    backend_ready = widget is not None and agent is not None and leads is not None
    backend_status(backend_ready)

    widget = widget or {}
    agent = agent or {}
    leads = leads or {"total": 0, "leads": []}

    enabled_tools = agent.get("enabled_tools", [])
    widget_ready = bool(widget.get("embed_snippet"))
    guardrails_ready = True

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric_card("Business", BUSINESS_NAME, CURRENT_PLAN, "blue")
    with col2:
        metric_card("Widget", "Ready" if widget_ready else "Needs setup", "Installable chat widget.", "success" if widget_ready else "warning")
    with col3:
        metric_card("Leads", leads.get("total", 0), "Contacts captured from visitors.", "success")
    with col4:
        metric_card("Safety", "On" if guardrails_ready else "Review", "Required protections enabled.", "success")

    st.divider()
    left, right = st.columns([1.1, 0.9], gap="large")
    with left:
        st.subheader("Quick Actions")
        a, b = st.columns(2)
        with a:
            _quick_action("Configure AI Agent", "AI Agent")
            _quick_action("Copy Install Snippet", "Install Widget")
        with b:
            _quick_action("Update Widget", "Widget")
            _quick_action("View Leads", "Leads")

        st.subheader("Assistant Capabilities")
        if enabled_tools:
            badge_row([(tool_name(tool), "locked") for tool in enabled_tools])
        else:
            empty_state("No assistant tools enabled", "Choose what your assistant can do from the AI Agent page.")
    with right:
        st.subheader("Business Status")
        badge_row([("Active", "success"), ("Admin access", "locked"), ("Business data only", "locked")])
        info_card(
            "Visitor widget",
            widget.get("greeting", "Hi! How can I help you?"),
            "soft",
        )
        domains = widget.get("allowed_origins", [])
        st.caption("Approved websites")
        if domains:
            for domain in domains:
                st.code(domain, language=None)
        else:
            st.caption("Add approved websites from the Widget page.")

    st.subheader("Recent Leads")
    recent_leads = leads.get("leads", [])
    if recent_leads:
        st.dataframe(recent_leads, use_container_width=True, hide_index=True)
    else:
        empty_state("No leads yet", "When visitors share contact details through the widget, they will appear here.")


def render_business_profile() -> None:
    page_header(
        "Business Profile",
        "Review your business workspace, admin access, and approved websites.",
        "Settings",
    )
    widget = get_widget_config() or {}
    backend_status(bool(widget))

    col1, col2, col3 = st.columns(3)
    with col1:
        metric_card("Business Name", BUSINESS_NAME, "Shown internally for this demo workspace.", "blue")
    with col2:
        metric_card("Status", "Active", "Your concierge is available to configure.", "success")
    with col3:
        metric_card("Plan", CURRENT_PLAN, "Local demo configuration.")

    st.subheader("Admin")
    a, b = st.columns(2)
    with a:
        info_card("Admin email", st.session_state.get("email", "tenant admin"), "soft")
    with b:
        info_card("Security", "Secure tenant session. Business data only.", "soft")

    st.subheader("Allowed Websites")
    domains = widget.get("allowed_origins", [])
    if domains:
        for domain in domains:
            st.code(domain, language=None)
    else:
        empty_state("No websites approved yet", "Add the websites where your widget should appear.")


def render_content() -> None:
    page_header(
        "Content",
        "Manage the business knowledge your assistant will use when this area is connected.",
        "Knowledge",
    )
    badge_row([("Coming soon", "warning"), "FAQs", "Services", "Policies"])

    empty_state(
        "Content management is not connected yet",
        "Once connected, your FAQs, service pages, and policies will appear here.",
    )

    st.subheader("Content Library")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        info_card("FAQs", "Common customer questions and answers.", "soft")
    with col2:
        info_card("Services", "Products, packages, prices, and availability.", "soft")
    with col3:
        info_card("Policies", "Refunds, booking rules, warranties, and terms.", "soft")
    with col4:
        info_card("Contact Info", "Locations, phone numbers, hours, and links.", "soft")


def render_analytics() -> None:
    page_header(
        "Analytics",
        "Track visitor conversations, leads, handoffs, and usage once reporting is connected.",
        "Insights",
    )
    badge_row([("Coming soon", "warning"), "Conversations", "Leads", "Usage"])

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric_card("Conversations", "-", "Visitor chats over time.", "muted")
    with col2:
        metric_card("Leads", "-", "Contacts captured by the widget.", "muted")
    with col3:
        metric_card("Handoffs", "-", "Chats routed to a person.", "muted")
    with col4:
        metric_card("Usage Cost", "-", "Estimated AI usage.", "muted")

    st.subheader("Routing Breakdown")
    col1, col2 = st.columns(2)
    with col1:
        info_card("Workflow handled", "Structured flows and lead capture.", "soft")
    with col2:
        info_card("AI assistant handled", "Open-ended questions answered by the assistant.", "soft")


def render_sidebar() -> str:
    st.sidebar.title("Concierge")
    st.sidebar.caption("Business admin")
    st.sidebar.divider()

    if st.session_state["page"] not in NAV_ITEMS:
        st.session_state["page"] = "Dashboard"

    selected = st.sidebar.radio(
        "Navigate",
        NAV_ITEMS,
        index=NAV_ITEMS.index(st.session_state["page"]),
        label_visibility="collapsed",
    )
    st.session_state["page"] = selected

    st.sidebar.divider()
    st.sidebar.caption(st.session_state.get("email", "Signed-in admin"))
    st.sidebar.caption("Active workspace")
    if st.sidebar.button("Sign out", use_container_width=True):
        st.session_state.clear()
        st.rerun()
    return selected


if st.session_state["token"] is None:
    login_form()
else:
    page = render_sidebar()

    if page == "Dashboard":
        render_dashboard()
    elif page == "Business Profile":
        render_business_profile()
    elif page == "Content":
        render_content()
    elif page == "AI Agent":
        from views.agent_config import render

        render(mode="agent")
    elif page == "Safety Rules":
        from views.agent_config import render

        render(mode="safety")
    elif page == "Widget":
        from views.widget_config import render

        render(mode="config")
    elif page == "Install Widget":
        from views.widget_config import render

        render(mode="install")
    elif page == "Leads":
        from views.leads import render

        render()
    else:
        render_analytics()
