"""UI formatting and page-heading helpers."""

from datetime import date, datetime
from decimal import Decimal

import streamlit as st

from app.utils.currency import format_currency


def page_header(title: str, subtitle: str, eyebrow: str = "Operations workspace") -> None:
    st.markdown(f'<div class="eyebrow">{eyebrow}</div>', unsafe_allow_html=True)
    st.title(title)
    st.markdown(f'<div class="page-subtitle">{subtitle}</div>', unsafe_allow_html=True)


def pretty_date(value: date | datetime | None) -> str:
    return value.strftime("%b %d, %Y") if value else "—"


def currency(value: Decimal | int | float | None, code: str) -> str:
    return format_currency(value, code)
