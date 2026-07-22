"""FieldOps Intelligence Streamlit entry point."""

import logging

import streamlit as st
from sqlalchemy import select

from app.database.models import Business
from app.database.seed import seed_demo_data
from app.database.session import create_schema, session_scope
from app.ui.components.states import demo_banner
from app.ui.navigation import PAGES
from app.ui.theme import apply_theme
from app.utils.logging import configure_logging

st.set_page_config(
    page_title="FieldOps Intelligence",
    page_icon="◼",
    layout="wide",
    initial_sidebar_state="expanded",
)
configure_logging()
apply_theme()


def ensure_business() -> Business | None:
    """Return the first local business; offer safe demo initialization when empty."""
    create_schema()
    with session_scope() as session:
        return session.scalar(select(Business).order_by(Business.id).limit(1))


business = ensure_business()
with st.sidebar:
    st.markdown('<div class="product-mark">FieldOps Intelligence</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="product-tagline">Clearer operations. Better decisions.</div>',
        unsafe_allow_html=True,
    )
    if business:
        st.caption(business.name)
    selected_page = st.radio("Workspace", list(PAGES), label_visibility="collapsed")
    st.markdown("---")
    st.caption("Local-first MVP · v0.1.0")

if business is None:
    st.title("Set up your workspace")
    st.write("The database is ready but contains no business records.")
    if st.button("Load synthetic demo workspace", type="primary"):
        try:
            with session_scope() as session:
                seed_demo_data(session)
            st.success("Demo workspace created.")
            st.rerun()
        except Exception:
            logging.exception("Demo initialization failed")
            st.error("The demo workspace could not be initialized. Check the application log.")
    st.stop()

if business.settings.get("demo_data"):
    demo_banner()

try:
    PAGES[selected_page](business.id, business.currency_code)
except Exception:
    logging.exception("Page rendering failed: %s", selected_page)
    st.error(
        "This page could not be loaded. Technical details were written to the application log."
    )
