"""FieldOps Intelligence Streamlit entry point."""

import logging

import streamlit as st
from pydantic import ValidationError

from app.database.models import Business
from app.database.session import (
    WorkspaceMode,
    create_schema,
    session_scope,
    set_active_workspace,
)
from app.schemas.business import BusinessCreate
from app.services.workspace_service import WorkspaceService, should_show_demo_banner
from app.ui.components.states import demo_banner
from app.ui.navigation import PAGES
from app.ui.theme import apply_theme
from app.utils.logging import configure_logging
from app.utils.validation import DomainError

WORKSPACE_STATE_KEY = "fieldops_workspace_mode"

st.set_page_config(
    page_title="FieldOps Intelligence",
    page_icon="◼",
    layout="wide",
    initial_sidebar_state="expanded",
)
configure_logging()
apply_theme()


def load_business(workspace: WorkspaceMode) -> Business | None:
    """Return the business in one explicit physical workspace."""
    create_schema(workspace=workspace)
    with session_scope(workspace=workspace) as session:
        return WorkspaceService(session).get_business()


def choose_workspace(workspace: WorkspaceMode) -> None:
    st.session_state[WORKSPACE_STATE_KEY] = workspace.value


operational_business = load_business(WorkspaceMode.OPERATIONAL)
requested_mode = st.session_state.get(WORKSPACE_STATE_KEY)
workspace_mode = (
    WorkspaceMode.DEMO if requested_mode == WorkspaceMode.DEMO.value else WorkspaceMode.OPERATIONAL
)
business = (
    load_business(WorkspaceMode.DEMO)
    if workspace_mode == WorkspaceMode.DEMO
    else operational_business
)

with st.sidebar:
    st.markdown('<div class="product-mark">FieldOps Intelligence</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="product-tagline">Clearer operations. Better decisions.</div>',
        unsafe_allow_html=True,
    )

if business is None:
    st.title("Set up your workspace")
    st.write(
        "Choose a blank operational workspace for real business records or a completely separate synthetic demo workspace."
    )
    real_column, demo_column = st.columns(2)
    with real_column:
        st.subheader("Create a real workspace")
        st.caption("Creates only your business profile in the operational database.")
        with st.form("real_workspace_setup"):
            name = st.text_input("Business name *")
            industry = st.text_input("Industry *", "Field services")
            currency = st.text_input("Currency code *", "CAD")
            timezone = st.text_input("Timezone *", "America/Toronto")
            create_real = st.form_submit_button("Create a real workspace", type="primary")
        if create_real:
            try:
                payload = BusinessCreate(
                    name=name,
                    industry=industry,
                    currency_code=currency,
                    timezone=timezone,
                )
                with session_scope(workspace=WorkspaceMode.OPERATIONAL) as session:
                    WorkspaceService(session).create_operational_workspace(payload)
                choose_workspace(WorkspaceMode.OPERATIONAL)
                st.success("Blank operational workspace created.")
                st.rerun()
            except (ValidationError, DomainError) as exc:
                st.error(str(exc))
    with demo_column:
        st.subheader("Load the demo workspace")
        st.caption(
            "Uses deterministic synthetic data in the dedicated demo database. It never writes to the operational database."
        )
        if st.button("Load the demo workspace"):
            try:
                create_schema(workspace=WorkspaceMode.DEMO)
                with session_scope(workspace=WorkspaceMode.DEMO) as session:
                    WorkspaceService(session).initialize_demo_workspace()
                choose_workspace(WorkspaceMode.DEMO)
                st.success("Separate demo workspace ready.")
                st.rerun()
            except (ValueError, DomainError):
                logging.exception("Demo initialization failed")
                st.error("The demo workspace could not be initialized. Check the application log.")
    st.stop()

set_active_workspace(workspace_mode)
with st.sidebar:
    st.caption(business.name)
    if workspace_mode == WorkspaceMode.DEMO:
        st.warning("DEMO MODE · synthetic data")
    else:
        st.markdown(
            '<div class="env-label">Summit pilot · operational</div>', unsafe_allow_html=True
        )
    selected_page = st.radio("Workspace", list(PAGES), label_visibility="collapsed")
    st.markdown("---")
    if workspace_mode == WorkspaceMode.DEMO:
        if operational_business is not None:
            if st.button("Return to real workspace", use_container_width=True):
                choose_workspace(WorkspaceMode.OPERATIONAL)
                st.rerun()
        elif st.button("Create a real workspace", use_container_width=True):
            choose_workspace(WorkspaceMode.OPERATIONAL)
            st.rerun()
        if st.button("Reset demo workspace", use_container_width=True):
            try:
                with session_scope(workspace=WorkspaceMode.DEMO) as session:
                    business = WorkspaceService(session).reset_demo_workspace()
                st.success("Demo data reset. Operational data was not touched.")
                st.rerun()
            except (ValueError, DomainError):
                logging.exception("Demo reset failed")
                st.error("The demo workspace could not be reset. Check the application log.")
    elif st.button("Open demo workspace", use_container_width=True):
        try:
            create_schema(workspace=WorkspaceMode.DEMO)
            with session_scope(workspace=WorkspaceMode.DEMO) as session:
                WorkspaceService(session).initialize_demo_workspace()
            choose_workspace(WorkspaceMode.DEMO)
            st.rerun()
        except (ValueError, DomainError):
            logging.exception("Demo initialization failed")
            st.error("The demo workspace could not be initialized. Check the application log.")
    st.caption("Summit Pilot")

if should_show_demo_banner(workspace_mode, business):
    demo_banner()

try:
    PAGES[selected_page](business.id, business.currency_code)
except Exception:
    logging.exception("Page rendering failed: %s", selected_page)
    st.error(
        "This page could not be loaded. Technical details were written to the application log."
    )
