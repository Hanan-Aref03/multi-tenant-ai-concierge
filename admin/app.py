"""Concierge Tenant Admin — Streamlit app entry point."""
import streamlit as st

st.set_page_config(page_title="Concierge Admin", layout="wide")

if "token" not in st.session_state:
    st.session_state["token"] = None

def login_form() -> None:
    st.title("Concierge Admin")
    st.subheader("Sign in")
    with st.form("login"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in")
    if submitted:
        # Phase 5 wires this to POST /api/auth/login — stub for now
        if email and password:
            st.session_state["token"] = "stub-token"
            st.session_state["email"] = email
            st.rerun()
        else:
            st.error("Enter email and password")

if st.session_state["token"] is None:
    login_form()
else:
    st.sidebar.title("Concierge Admin")
    st.sidebar.write(f"Signed in as {st.session_state.get('email', '')}")
    if st.sidebar.button("Sign out"):
        st.session_state.clear()
        st.rerun()

    page = st.sidebar.radio("Navigate", ["Widget Config", "Agent Config", "Leads"])

    if page == "Widget Config":
        import pages.widget_config  # noqa: F401
    elif page == "Agent Config":
        import pages.agent_config  # noqa: F401
    else:
        import pages.leads  # noqa: F401
