"""Widget Config admin page — greeting, theme, allowed origins, embed snippet."""
import streamlit as st

from api_client import get_widget_config, update_widget_config

st.title("Widget Configuration")

data = get_widget_config()
if data is None:
    st.stop()

with st.form("widget_form"):
    st.subheader("Appearance")
    greeting = st.text_input("Greeting message", value=data.get("greeting", ""))
    accent_colour = st.color_picker("Accent colour", value=data.get("accent_colour", "#3B82F6"))

    st.subheader("Allowed Origins")
    st.caption("Domains allowed to embed this widget. One per line, e.g. https://acme.com")
    origins_text = st.text_area(
        "Allowed origins",
        value="\n".join(data.get("allowed_origins", [])),
        height=120,
    )

    saved = st.form_submit_button("Save changes")

if saved:
    origins = [o.strip() for o in origins_text.splitlines() if o.strip()]
    result = update_widget_config(greeting, accent_colour, origins)
    if result:
        st.success("Widget config saved.")
        st.rerun()

st.divider()
st.subheader("Embed Snippet")
st.caption("Paste this into your website's HTML to embed the widget.")
snippet = data.get("embed_snippet", "")
st.code(snippet, language="html")
st.button("Copy", on_click=lambda: st.write("Copied!"))  # browser copy handled via JS in real app
