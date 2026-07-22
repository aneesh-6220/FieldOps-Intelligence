"""Customer directory, editing, and job history."""

from decimal import Decimal

import streamlit as st
from pydantic import ValidationError
from sqlalchemy import select

from app.database.models import Customer
from app.database.models.enums import CustomerStatus, LeadSource
from app.database.repositories import CustomerRepository
from app.database.session import session_scope
from app.schemas.customer import CustomerCreate, CustomerUpdate
from app.services.customer_service import CustomerService
from app.ui.components.states import empty_state
from app.ui.formatting import currency, page_header, pretty_date
from app.utils.validation import DomainError


def render(business_id: int, currency_code: str) -> None:
    page_header(
        "Customers",
        "Maintain customer details and see every job and realized dollar in one history.",
        "Customer records",
    )
    with session_scope() as session:
        customers = list(
            session.scalars(
                select(Customer)
                .where(Customer.business_id == business_id)
                .order_by(Customer.last_name)
            ).all()
        )
    tabs = st.tabs(["Directory", "Add", "Edit", "History"])
    with tabs[0]:
        search = st.text_input("Search customers")
        shown = [
            item for item in customers if not search or search.lower() in item.display_name.lower()
        ]
        if not shown:
            empty_state("No customers match", "Adjust the search or create a customer.")
        else:
            st.dataframe(
                [
                    {
                        "ID": item.id,
                        "Customer": item.display_name,
                        "Status": item.customer_status.label,
                        "City": item.city or "—",
                        "Email": item.email or "—",
                        "Phone": item.phone or "—",
                        "Source": item.acquisition_source.label if item.acquisition_source else "—",
                    }
                    for item in shown
                ],
                hide_index=True,
                use_container_width=True,
            )
    with tabs[1]:
        with st.form("customer_create", clear_on_submit=True):
            row = st.columns(3)
            first = row[0].text_input("First name *")
            last = row[1].text_input("Last name")
            company = row[2].text_input("Company")
            row = st.columns(3)
            email = row[0].text_input("Email")
            phone = row[1].text_input("Phone")
            source = row[2].selectbox(
                "Acquisition source", list(LeadSource), format_func=lambda value: value.label
            )
            row = st.columns(4)
            address = row[0].text_input("Street address")
            city = row[1].text_input("City")
            region = row[2].text_input("Province / state")
            postal = row[3].text_input("Postal code")
            notes = st.text_area("Notes")
            submitted = st.form_submit_button("Create customer", type="primary")
        if submitted:
            try:
                payload = CustomerCreate(
                    business_id=business_id,
                    first_name=first,
                    last_name=last,
                    company_name=company or None,
                    email=email or None,
                    phone=phone or None,
                    street_address=address or None,
                    city=city or None,
                    province_or_state=region or None,
                    postal_code=postal or None,
                    acquisition_source=source,
                    notes=notes or None,
                )
                with session_scope() as session:
                    CustomerService(session).create(payload)
                st.success("Customer created.")
                st.rerun()
            except ValidationError as exc:
                st.error(str(exc))
    with tabs[2]:
        if not customers:
            st.caption("Create a customer before editing.")
        else:
            customer_id = st.selectbox(
                "Customer to edit",
                [item.id for item in customers],
                format_func=lambda value: next(
                    item.display_name for item in customers if item.id == value
                ),
                key="edit_customer_id",
            )
            selected = next(item for item in customers if item.id == customer_id)
            with st.form("customer_edit"):
                row = st.columns(3)
                first = row[0].text_input("First name", selected.first_name)
                last = row[1].text_input("Last name", selected.last_name)
                company = row[2].text_input("Company", selected.company_name or "")
                row = st.columns(3)
                email = row[0].text_input("Email", selected.email or "")
                phone = row[1].text_input("Phone", selected.phone or "")
                source = row[2].selectbox(
                    "Source",
                    list(LeadSource),
                    index=list(LeadSource).index(selected.acquisition_source)
                    if selected.acquisition_source
                    else 0,
                    format_func=lambda value: value.label,
                )
                row = st.columns(4)
                address = row[0].text_input("Street address", selected.street_address or "")
                city = row[1].text_input("City", selected.city or "")
                region = row[2].text_input("Province / state", selected.province_or_state or "")
                postal = row[3].text_input("Postal code", selected.postal_code or "")
                status = st.selectbox(
                    "Status",
                    list(CustomerStatus),
                    index=list(CustomerStatus).index(selected.customer_status),
                    format_func=lambda value: value.label,
                )
                notes = st.text_area("Notes", selected.notes or "")
                submitted = st.form_submit_button("Save customer")
            if submitted:
                try:
                    payload = CustomerUpdate(
                        business_id=business_id,
                        first_name=first,
                        last_name=last,
                        company_name=company or None,
                        email=email or None,
                        phone=phone or None,
                        street_address=address or None,
                        city=city or None,
                        province_or_state=region or None,
                        postal_code=postal or None,
                        acquisition_source=source,
                        notes=notes or None,
                        customer_status=status,
                    )
                    with session_scope() as session:
                        CustomerService(session).update(customer_id, business_id, payload)
                    st.success("Customer updated.")
                    st.rerun()
                except (ValidationError, DomainError) as exc:
                    st.error(str(exc))
    with tabs[3]:
        if not customers:
            empty_state("No customer history", "Create or convert a lead first.")
        else:
            customer_id = st.selectbox(
                "Customer",
                [item.id for item in customers],
                format_func=lambda value: next(
                    item.display_name for item in customers if item.id == value
                ),
                key="history_customer_id",
            )
            with session_scope() as session:
                customer = CustomerRepository(session).with_history(customer_id, business_id)
                realized = sum(
                    (job.final_revenue or Decimal("0") for job in customer.jobs), Decimal("0")
                )
                history = sorted(customer.jobs, key=lambda job: job.created_at, reverse=True)
            row = st.columns(3)
            row[0].metric("Jobs", len(history))
            row[1].metric("Realized revenue", currency(realized, currency_code))
            row[2].metric("Repeat customer", "Yes" if len(history) >= 2 else "No")
            st.dataframe(
                [
                    {
                        "Date": pretty_date(job.completed_at or job.created_at),
                        "Job": job.job_number,
                        "Service": job.service.name if job.service else "Uncategorized",
                        "Status": job.status.label,
                        "Final revenue": currency(job.final_revenue, currency_code)
                        if job.final_revenue is not None
                        else "—",
                        "Originating lead": job.originating_lead.contact_name
                        if job.originating_lead
                        else "Manual job",
                    }
                    for job in history
                ],
                hide_index=True,
                use_container_width=True,
            )
