"""Configurable Phase 1 service catalog."""

from decimal import Decimal

import streamlit as st
from pydantic import ValidationError
from sqlalchemy import select

from app.database.models import Service
from app.database.models.enums import PricingModel
from app.database.session import session_scope
from app.schemas.service import ServiceCreate
from app.services.service_service import ServiceCatalogService
from app.ui.components.states import empty_state
from app.ui.formatting import currency, page_header


def render(business_id: int, currency_code: str) -> None:
    page_header(
        "Services",
        "Configure the offerings that categorize leads, jobs, duration assumptions, and revenue.",
        "Service catalog",
    )
    with session_scope() as session:
        services = list(
            session.scalars(
                select(Service).where(Service.business_id == business_id).order_by(Service.name)
            ).all()
        )
    tabs = st.tabs(["Catalog", "Add", "Edit"])
    with tabs[0]:
        if not services:
            empty_state(
                "No services configured", "Add a service to unlock lead and job categories."
            )
        else:
            st.dataframe(
                [
                    {
                        "ID": item.id,
                        "Service": item.name,
                        "Category": item.category,
                        "Pricing": item.pricing_model.label,
                        "Base price": currency(item.base_price, currency_code),
                        "Default cost": currency(item.default_cost, currency_code),
                        "Duration": f"{item.estimated_duration_minutes} min",
                        "Seasonal": item.seasonal,
                        "Active": item.is_active,
                    }
                    for item in services
                ],
                hide_index=True,
                use_container_width=True,
            )
    with tabs[1]:
        with st.form("service_create", clear_on_submit=True):
            row = st.columns(3)
            name = row[0].text_input("Name *")
            category = row[1].text_input("Category *")
            pricing = row[2].selectbox(
                "Pricing model", list(PricingModel), format_func=lambda value: value.label
            )
            row = st.columns(4)
            price = row[0].number_input("Base price", min_value=0.0)
            cost = row[1].number_input("Default cost", min_value=0.0)
            duration = row[2].number_input("Duration (minutes)", min_value=1, value=60)
            seasonal = row[3].checkbox("Seasonal")
            description = st.text_area("Description")
            submitted = st.form_submit_button("Add service", type="primary")
        if submitted:
            try:
                payload = ServiceCreate(
                    business_id=business_id,
                    name=name,
                    category=category,
                    description=description or None,
                    pricing_model=pricing,
                    base_price=Decimal(str(price)),
                    default_cost=Decimal(str(cost)),
                    estimated_duration_minutes=int(duration),
                    seasonal=seasonal,
                )
                with session_scope() as session:
                    ServiceCatalogService(session).create(payload)
                st.success("Service added.")
                st.rerun()
            except ValidationError as exc:
                st.error(str(exc))
    with tabs[2]:
        if not services:
            st.caption("No services are available to edit.")
        else:
            service_id = st.selectbox(
                "Service",
                [item.id for item in services],
                format_func=lambda value: next(item.name for item in services if item.id == value),
            )
            selected = next(item for item in services if item.id == service_id)
            with st.form("service_edit"):
                row = st.columns(3)
                name = row[0].text_input("Name", selected.name)
                category = row[1].text_input("Category", selected.category)
                pricing = row[2].selectbox(
                    "Pricing model",
                    list(PricingModel),
                    index=list(PricingModel).index(selected.pricing_model),
                    format_func=lambda value: value.label,
                )
                row = st.columns(4)
                price = row[0].number_input(
                    "Base price", min_value=0.0, value=float(selected.base_price)
                )
                cost = row[1].number_input(
                    "Default cost", min_value=0.0, value=float(selected.default_cost)
                )
                duration = row[2].number_input(
                    "Duration (minutes)",
                    min_value=1,
                    value=selected.estimated_duration_minutes,
                )
                seasonal = row[3].checkbox("Seasonal", selected.seasonal)
                description = st.text_area("Description", selected.description or "")
                active = st.checkbox("Active", selected.is_active)
                submitted = st.form_submit_button("Save service")
            if submitted:
                try:
                    payload = ServiceCreate(
                        business_id=business_id,
                        name=name,
                        category=category,
                        description=description or None,
                        pricing_model=pricing,
                        base_price=Decimal(str(price)),
                        default_cost=Decimal(str(cost)),
                        estimated_duration_minutes=int(duration),
                        seasonal=seasonal,
                        is_active=active,
                    )
                    with session_scope() as session:
                        ServiceCatalogService(session).update(service_id, business_id, payload)
                    st.success("Service updated; historical job links remain intact.")
                    st.rerun()
                except ValidationError as exc:
                    st.error(str(exc))
