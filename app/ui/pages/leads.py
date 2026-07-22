"""Lead capture, editing, lifecycle, and transactional conversion UI."""

from datetime import date, datetime, time, timedelta
from decimal import Decimal

import streamlit as st
from pydantic import ValidationError
from sqlalchemy import func, select

from app.database.models import Job, Service, Worker
from app.database.models.enums import CustomerStatus, LeadSource, LeadStatus, Priority
from app.database.repositories import LeadRepository
from app.database.session import session_scope
from app.schemas.customer import CustomerCreate
from app.schemas.job import ConversionJobCreate
from app.schemas.lead import LeadConversion, LeadCreate, LeadUpdate
from app.services.job_service import JobService, ScheduleConflict
from app.services.lead_service import TRANSITIONS, LeadService
from app.ui.components.states import empty_state
from app.ui.formatting import currency, page_header
from app.utils.validation import DomainError


def render(business_id: int, currency_code: str) -> None:
    page_header(
        "Leads",
        "Capture demand, keep follow-ups visible, qualify the right work, and convert it into an editable customer and job proposal.",
        "Sales pipeline",
    )
    with session_scope() as session:
        services = list(
            session.scalars(
                select(Service).where(Service.business_id == business_id, Service.is_active)
            ).all()
        )
        workers = list(
            session.scalars(
                select(Worker).where(Worker.business_id == business_id, Worker.is_active)
            ).all()
        )
        pipeline = LeadRepository(session).pipeline(business_id)
        next_job = (
            session.scalar(select(func.count(Job.id)).where(Job.business_id == business_id)) or 0
        ) + 1
    service_by_name = {service.name: service for service in services}
    worker_by_name = {worker.display_name: worker for worker in workers}

    tabs = st.tabs(["Pipeline", "Add", "Edit", "Advance", "Convert"])
    with tabs[0]:
        filters = st.columns([1, 1, 1.2])
        status_filter = filters[0].multiselect(
            "Status", list(LeadStatus), format_func=lambda value: value.label
        )
        source_filter = filters[1].multiselect(
            "Source", list(LeadSource), format_func=lambda value: value.label
        )
        search = filters[2].text_input("Search contacts")
        shown = [
            lead
            for lead in pipeline
            if (not status_filter or lead.status in status_filter)
            and (not source_filter or lead.source in source_filter)
            and (not search or search.lower() in lead.contact_name.lower())
        ]
        if not shown:
            empty_state("No leads match this view", "Adjust filters or capture a new lead.")
        else:
            st.dataframe(
                [
                    {
                        "ID": lead.id,
                        "Contact": lead.contact_name,
                        "Service": lead.service.name if lead.service else "Unassigned",
                        "Owner": lead.assigned_worker.display_name
                        if lead.assigned_worker
                        else "Unassigned",
                        "Status": lead.status.label,
                        "Priority": lead.priority.label,
                        "Source": lead.source.label,
                        "Value": currency(lead.estimated_value, currency_code),
                        "Follow-up": lead.next_follow_up_date,
                    }
                    for lead in shown
                ],
                hide_index=True,
                use_container_width=True,
            )

    with tabs[1]:
        with st.form("lead_create", clear_on_submit=True):
            row = st.columns(3)
            contact = row[0].text_input("Contact name *")
            email = row[1].text_input("Email")
            phone = row[2].text_input("Phone")
            row = st.columns(4)
            service_name = row[0].selectbox("Service", ["Unassigned", *service_by_name])
            source = row[1].selectbox(
                "Source", list(LeadSource), format_func=lambda value: value.label
            )
            priority = row[2].selectbox(
                "Priority", list(Priority), index=1, format_func=lambda value: value.label
            )
            value = row[3].number_input("Estimated value", min_value=0.0, step=25.0)
            row = st.columns(4)
            address = row[0].text_input("Address")
            city = row[1].text_input("City")
            postal = row[2].text_input("Postal code")
            worker_name = row[3].selectbox("Owner", ["Unassigned", *worker_by_name])
            follow_up = st.date_input("Next follow-up", date.today() + timedelta(days=3))
            notes = st.text_area("Notes")
            submitted = st.form_submit_button("Create lead", type="primary")
        if submitted:
            try:
                payload = LeadCreate(
                    business_id=business_id,
                    contact_name=contact,
                    email=email or None,
                    phone=phone or None,
                    address=address or None,
                    city=city or None,
                    postal_code=postal or None,
                    service_id=service_by_name[service_name].id
                    if service_name in service_by_name
                    else None,
                    source=source,
                    estimated_value=Decimal(str(value)),
                    priority=priority,
                    assigned_worker_id=worker_by_name[worker_name].id
                    if worker_name in worker_by_name
                    else None,
                    next_follow_up_date=follow_up,
                    notes=notes or None,
                )
                with session_scope() as session:
                    LeadService(session).create(payload)
                st.success("Lead created.")
                st.rerun()
            except (ValidationError, DomainError) as exc:
                st.error(str(exc))

    with tabs[2]:
        editable = [
            lead for lead in pipeline if lead.status not in {LeadStatus.CONVERTED, LeadStatus.LOST}
        ]
        if not editable:
            st.caption("No open leads are available to edit.")
        else:
            lead_id = st.selectbox(
                "Lead to edit",
                [lead.id for lead in editable],
                format_func=lambda value: next(
                    item.contact_name for item in editable if item.id == value
                ),
                key="edit_lead_id",
            )
            selected = next(item for item in editable if item.id == lead_id)
            service_names = ["Unassigned", *service_by_name]
            current_service = selected.service.name if selected.service else "Unassigned"
            worker_names = ["Unassigned", *worker_by_name]
            current_worker = (
                selected.assigned_worker.display_name if selected.assigned_worker else "Unassigned"
            )
            with st.form("lead_edit"):
                row = st.columns(3)
                contact = row[0].text_input("Contact name", selected.contact_name)
                email = row[1].text_input("Email", selected.email or "")
                phone = row[2].text_input("Phone", selected.phone or "")
                row = st.columns(4)
                service_name = row[0].selectbox(
                    "Service", service_names, index=service_names.index(current_service)
                )
                source = row[1].selectbox(
                    "Source",
                    list(LeadSource),
                    index=list(LeadSource).index(selected.source),
                    format_func=lambda value: value.label,
                )
                priority = row[2].selectbox(
                    "Priority",
                    list(Priority),
                    index=list(Priority).index(selected.priority),
                    format_func=lambda value: value.label,
                )
                value = row[3].number_input(
                    "Estimated value", min_value=0.0, value=float(selected.estimated_value)
                )
                row = st.columns(4)
                address = row[0].text_input("Address", selected.address or "")
                city = row[1].text_input("City", selected.city or "")
                postal = row[2].text_input("Postal code", selected.postal_code or "")
                worker_name = row[3].selectbox(
                    "Owner", worker_names, index=worker_names.index(current_worker)
                )
                follow_up = st.date_input(
                    "Next follow-up", selected.next_follow_up_date or date.today()
                )
                notes = st.text_area("Notes", selected.notes or "")
                submitted = st.form_submit_button("Save lead")
            if submitted:
                try:
                    payload = LeadUpdate(
                        business_id=business_id,
                        contact_name=contact,
                        email=email or None,
                        phone=phone or None,
                        address=address or None,
                        city=city or None,
                        postal_code=postal or None,
                        service_id=service_by_name[service_name].id
                        if service_name in service_by_name
                        else None,
                        source=source,
                        estimated_value=Decimal(str(value)),
                        status=selected.status,
                        priority=priority,
                        assigned_worker_id=worker_by_name[worker_name].id
                        if worker_name in worker_by_name
                        else None,
                        next_follow_up_date=follow_up,
                        notes=notes or None,
                    )
                    with session_scope() as session:
                        LeadService(session).update(lead_id, business_id, payload)
                    st.success("Lead updated.")
                    st.rerun()
                except (ValidationError, DomainError) as exc:
                    st.error(str(exc))

    with tabs[3]:
        active = [lead for lead in pipeline if TRANSITIONS[lead.status]]
        if not active:
            st.caption("No leads have available transitions.")
        else:
            lead_id = st.selectbox(
                "Lead",
                [lead.id for lead in active],
                format_func=lambda value: next(
                    f"{item.contact_name} · {item.status.label}"
                    for item in active
                    if item.id == value
                ),
                key="advance_lead_id",
            )
            selected = next(item for item in active if item.id == lead_id)
            target = st.selectbox(
                "Move to",
                sorted(TRANSITIONS[selected.status], key=lambda value: value.value),
                format_func=lambda value: value.label,
            )
            lost_reason = st.text_input("Lost reason") if target == LeadStatus.LOST else None
            if st.button("Update status"):
                try:
                    with session_scope() as session:
                        LeadService(session).transition(
                            selected.id, business_id, target, lost_reason
                        )
                    st.success(f"Lead moved to {target.label}.")
                    st.rerun()
                except DomainError as exc:
                    st.error(str(exc))

    with tabs[4]:
        qualified = [lead for lead in pipeline if lead.status == LeadStatus.QUALIFIED]
        if not qualified:
            empty_state(
                "No qualified leads awaiting conversion",
                "Move a suitable lead to Qualified before creating its customer and job.",
            )
        else:
            lead_id = st.selectbox(
                "Qualified lead",
                [lead.id for lead in qualified],
                format_func=lambda value: next(
                    f"{item.contact_name} · {currency(item.estimated_value, currency_code)}"
                    for item in qualified
                    if item.id == value
                ),
                key="convert_lead_id",
            )
            selected = next(item for item in qualified if item.id == lead_id)
            names = selected.contact_name.split(maxsplit=1)
            selected_service = selected.service
            with st.form("lead_conversion"):
                st.markdown("**Review customer details**")
                row = st.columns(3)
                first_name = row[0].text_input("First name", names[0])
                last_name = row[1].text_input("Last name", names[1] if len(names) > 1 else "")
                company = row[2].text_input("Company name")
                row = st.columns(3)
                customer_email = row[0].text_input("Customer email", selected.email or "")
                customer_phone = row[1].text_input("Customer phone", selected.phone or "")
                province = row[2].text_input("Province / state", "Ontario")
                st.markdown("**Review job details**")
                row = st.columns(3)
                job_number = row[0].text_input(
                    "Job number", f"JOB-{date.today().year}-{next_job:04d}"
                )
                job_title = row[1].text_input(
                    "Job title", selected_service.name if selected_service else "Field service job"
                )
                service_name = row[2].selectbox(
                    "Service",
                    ["Unassigned", *service_by_name],
                    index=(
                        ["Unassigned", *service_by_name].index(selected_service.name)
                        if selected_service
                        else 0
                    ),
                )
                row = st.columns(4)
                schedule_now = row[0].checkbox("Schedule now")
                job_date = row[1].date_input(
                    "Job date", date.today() + timedelta(days=7), disabled=not schedule_now
                )
                job_time = row[2].time_input("Start time", time(9), disabled=not schedule_now)
                duration = row[3].number_input(
                    "Hours", min_value=0.5, value=2.0, step=0.5, disabled=not schedule_now
                )
                row = st.columns(4)
                quoted = row[0].number_input(
                    "Quoted revenue", min_value=0.0, value=float(selected.estimated_value)
                )
                estimated_cost = row[1].number_input(
                    "Estimated cost",
                    min_value=0.0,
                    value=float(selected_service.default_cost) if selected_service else 0.0,
                )
                worker_name = row[2].selectbox("Initial worker", ["Assign later", *worker_by_name])
                expected_hours = row[3].number_input(
                    "Expected worker hours", min_value=0.0, value=2.0, step=0.5
                )
                acknowledge = st.checkbox(
                    "I reviewed the customer and job details and confirm this conversion."
                )
                acknowledge_conflict = st.checkbox(
                    "If the selected worker has an overlap, I acknowledge and want to proceed."
                )
                submitted = st.form_submit_button("Create customer and job", type="primary")
            if submitted:
                try:
                    start = datetime.combine(job_date, job_time) if schedule_now else None
                    customer = CustomerCreate(
                        business_id=business_id,
                        first_name=first_name,
                        last_name=last_name,
                        company_name=company or None,
                        email=customer_email or None,
                        phone=customer_phone or None,
                        street_address=selected.address,
                        city=selected.city,
                        province_or_state=province or None,
                        postal_code=selected.postal_code,
                        acquisition_source=selected.source,
                        notes="Created from qualified lead conversion.",
                        customer_status=CustomerStatus.ACTIVE,
                    )
                    job = ConversionJobCreate(
                        service_id=service_by_name[service_name].id
                        if service_name in service_by_name
                        else None,
                        job_number=job_number,
                        title=job_title,
                        priority=selected.priority,
                        scheduled_start=start,
                        scheduled_end=start + timedelta(hours=duration) if start else None,
                        street_address=selected.address,
                        city=selected.city,
                        postal_code=selected.postal_code,
                        quoted_revenue=Decimal(str(quoted)),
                        estimated_cost=Decimal(str(estimated_cost)),
                        notes="Created from qualified lead conversion.",
                    )
                    conversion = LeadConversion(
                        lead_id=selected.id,
                        business_id=business_id,
                        customer=customer,
                        job=job,
                        confirmed=acknowledge,
                    )
                    with session_scope() as session:
                        _, created_job = LeadService(session).convert(conversion)
                        if worker_name in worker_by_name:
                            JobService(session).assign_worker(
                                created_job.id,
                                business_id,
                                worker_by_name[worker_name].id,
                                Decimal(str(expected_hours)),
                                acknowledge_conflict=acknowledge_conflict,
                            )
                    st.success("Lead converted: customer and job created together.")
                    st.rerun()
                except (ValidationError, DomainError, ScheduleConflict) as exc:
                    st.error(str(exc))
