"""Business profile and Phase 1 operating thresholds."""

from decimal import Decimal

import streamlit as st
from pydantic import ValidationError

from app.database.models import Business
from app.database.session import WorkspaceMode, get_active_workspace, session_scope
from app.schemas.business import BusinessUpdate
from app.ui.formatting import page_header


def render(business_id: int, currency_code: str) -> None:
    del currency_code
    page_header(
        "Settings",
        "Adapt the workspace and its operating-alert thresholds without editing code.",
        "Workspace configuration",
    )
    with session_scope() as session:
        business = session.get(Business, business_id)
    if business is None:
        st.error("Business configuration was not found.")
        return
    with st.form("business_settings"):
        row = st.columns(3)
        name = row[0].text_input("Business name", business.name)
        industry = row[1].text_input("Industry", business.industry)
        email = row[2].text_input("Email", business.email or "")
        row = st.columns(4)
        phone = row[0].text_input("Phone", business.phone or "")
        city = row[1].text_input("City", business.city or "")
        region = row[2].text_input("Province / state", business.province_or_state or "")
        country = row[3].text_input("Country", business.country)
        row = st.columns(3)
        currency = row[0].text_input("Currency code", business.currency_code)
        timezone = row[1].text_input("Timezone", business.timezone)
        tax = row[2].number_input(
            "Default tax rate (%)",
            min_value=0.0,
            max_value=100.0,
            value=float(business.default_tax_rate * 100),
        )
        st.subheader("Operational insight thresholds")
        values = business.settings or {}
        row = st.columns(4)
        cost = row[0].number_input(
            "Cost overrun (%)",
            min_value=0.0,
            max_value=500.0,
            value=float(values.get("cost_overrun_threshold", 0.20)) * 100,
        )
        duration = row[1].number_input(
            "Duration overrun (%)",
            min_value=0.0,
            max_value=500.0,
            value=float(values.get("duration_overrun_threshold", 0.25)) * 100,
        )
        concentration = row[2].number_input(
            "Customer concentration (%)",
            min_value=0.0,
            max_value=100.0,
            value=float(values.get("concentration_threshold", 0.60)) * 100,
        )
        sample = row[3].number_input(
            "Low sample warning",
            min_value=2,
            value=int(values.get("low_sample_threshold", 5)),
        )
        submitted = st.form_submit_button("Save settings", type="primary")
    if submitted:
        try:
            payload = BusinessUpdate(
                name=name,
                industry=industry,
                email=email or None,
                phone=phone or None,
                city=city or None,
                province_or_state=region or None,
                country=country,
                currency_code=currency,
                timezone=timezone,
                default_tax_rate=Decimal(str(tax / 100)),
            )
            with session_scope() as session:
                target = session.get(Business, business_id)
                if target is None:
                    raise LookupError("Business configuration was not found")
                for key, value in payload.model_dump().items():
                    setattr(target, key, value)
                target.settings = {
                    **(target.settings or {}),
                    "demo_data": get_active_workspace() == WorkspaceMode.DEMO,
                    "cost_overrun_threshold": cost / 100,
                    "duration_overrun_threshold": duration / 100,
                    "concentration_threshold": concentration / 100,
                    "low_sample_threshold": int(sample),
                }
            st.success("Workspace settings saved.")
            st.rerun()
        except ValidationError as exc:
            st.error(str(exc))
    st.info("The database URL and log level remain environment-controlled infrastructure settings.")
