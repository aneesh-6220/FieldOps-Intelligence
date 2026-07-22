"""Compact KPI card component."""

import html

import streamlit as st


def metric_card(label: str, value: str, help_text: str) -> None:
    st.markdown(
        f"""<div class="metric-card"><div class="metric-label">{html.escape(label)}</div>
        <div class="metric-value">{html.escape(value)}</div><div class="metric-help">{html.escape(help_text)}</div></div>""",
        unsafe_allow_html=True,
    )
