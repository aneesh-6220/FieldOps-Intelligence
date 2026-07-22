"""Reusable empty and demo states."""

import streamlit as st


def empty_state(title: str, body: str) -> None:
    st.info(f"**{title}**\n\n{body}")


def demo_banner() -> None:
    st.markdown(
        '<div class="demo-banner">DEMO MODE — synthetic records in a separate demo database. Operational data is not shown or changed.</div>',
        unsafe_allow_html=True,
    )
