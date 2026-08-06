"""Phase 1 system scope and runtime information."""

import platform
import sys

import sqlalchemy
import streamlit as st

from app import __version__
from app.config import get_settings
from app.ui.formatting import page_header


def render(business_id: int, currency_code: str) -> None:
    del business_id, currency_code
    page_header(
        "About FieldOps Intelligence",
        "A Python-based operations intelligence platform for small field-service businesses.",
        "System information",
    )
    st.write(
        "Phase 1 proves one connected operating workflow: a lead is qualified, converted into a customer and job, assigned, completed, and reflected in the dashboard and analytics."
    )
    left, right = st.columns(2)
    with left:
        st.subheader("Runtime")
        st.code(
            f"Application  {__version__}\nPython       {sys.version.split()[0]}\n"
            f"Streamlit    {st.__version__}\nSQLAlchemy   {sqlalchemy.__version__}\n"
            f"Platform     {platform.system()} {platform.release()}"
        )
    with right:
        st.subheader("Deployment model")
        st.write(
            "Streamlit application with SQLAlchemy. Local development uses SQLite; the hosted Summit pilot uses managed PostgreSQL. Operational and demo records always live in separate databases."
        )
        settings = get_settings()
        st.code(
            f"Operational  {settings.database_dialect}\nDemo         {settings.demo_database_dialect}"
        )
        st.caption("Connection details are held in environment variables and are never displayed.")
    st.warning(
        "This is not a production SaaS. Real commercial use requires authentication, authorization, privacy and security review, backups, durable infrastructure, and tested recovery procedures."
    )
    with st.expander("Intentionally deferred"):
        st.write(
            "Estimates, invoices, payments, expenses, imports, maps, forecasting, statistical anomaly detection, external integrations, customer portals, mobile clients, and SaaS controls are Phase 2 or later work."
        )
