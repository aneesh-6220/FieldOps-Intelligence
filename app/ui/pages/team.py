"""Worker directory, editing, and assignment-load summary."""

from decimal import Decimal

import streamlit as st
from pydantic import ValidationError
from sqlalchemy import func, select

from app.database.models import JobAssignment, Worker
from app.database.models.enums import EmploymentStatus
from app.database.session import session_scope
from app.schemas.worker import WorkerCreate
from app.services.worker_service import WorkerService
from app.ui.components.states import empty_state
from app.ui.formatting import currency, page_header


def render(business_id: int, currency_code: str) -> None:
    page_header(
        "Team",
        "Maintain worker availability, skills, cost assumptions, and assignment load.",
        "Workforce coordination",
    )
    with session_scope() as session:
        workers = list(
            session.scalars(
                select(Worker).where(Worker.business_id == business_id).order_by(Worker.last_name)
            ).all()
        )
        count_rows = session.execute(
            select(JobAssignment.worker_id, func.count(JobAssignment.id)).group_by(
                JobAssignment.worker_id
            )
        ).all()
        counts = {int(worker_id): int(count) for worker_id, count in count_rows}
        hour_rows = session.execute(
            select(
                JobAssignment.worker_id,
                func.sum(JobAssignment.expected_hours),
                func.sum(JobAssignment.actual_hours),
            ).group_by(JobAssignment.worker_id)
        ).all()
        hours = {
            int(worker_id): (Decimal(expected or 0), Decimal(actual or 0))
            for worker_id, expected, actual in hour_rows
        }
    tabs = st.tabs(["Team", "Add", "Edit"])
    with tabs[0]:
        if not workers:
            empty_state("No team members", "Add a worker before assigning jobs.")
        else:
            st.dataframe(
                [
                    {
                        "Worker": worker.display_name,
                        "Role": worker.role,
                        "Employment": worker.employment_status.label,
                        "Hourly cost": currency(worker.hourly_cost, currency_code),
                        "Skills": ", ".join(worker.skills),
                        "Assignments": counts.get(worker.id, 0),
                        "Expected hours": float(hours.get(worker.id, (Decimal(0), Decimal(0)))[0]),
                        "Actual hours": float(hours.get(worker.id, (Decimal(0), Decimal(0)))[1]),
                        "Active": worker.is_active,
                    }
                    for worker in workers
                ],
                hide_index=True,
                use_container_width=True,
            )
            st.caption("Assignment hours are an operating proxy, not payroll time.")
    with tabs[1]:
        with st.form("worker_create", clear_on_submit=True):
            row = st.columns(4)
            first = row[0].text_input("First name *")
            last = row[1].text_input("Last name *")
            email = row[2].text_input("Email")
            phone = row[3].text_input("Phone")
            row = st.columns(3)
            role = row[0].text_input("Role", "Field technician")
            hourly = row[1].number_input("Hourly cost", min_value=0.0)
            status = row[2].selectbox(
                "Employment", list(EmploymentStatus), format_func=lambda value: value.label
            )
            skills = st.text_input("Skills", help="Comma-separated")
            submitted = st.form_submit_button("Add worker", type="primary")
        if submitted:
            try:
                payload = WorkerCreate(
                    business_id=business_id,
                    first_name=first,
                    last_name=last,
                    email=email or None,
                    phone=phone or None,
                    role=role,
                    hourly_cost=Decimal(str(hourly)),
                    employment_status=status,
                    skills=[item.strip() for item in skills.split(",") if item.strip()],
                )
                with session_scope() as session:
                    WorkerService(session).create(payload)
                st.success("Worker added.")
                st.rerun()
            except ValidationError as exc:
                st.error(str(exc))
    with tabs[2]:
        if not workers:
            st.caption("No workers are available to edit.")
        else:
            worker_id = st.selectbox(
                "Worker",
                [worker.id for worker in workers],
                format_func=lambda value: next(
                    worker.display_name for worker in workers if worker.id == value
                ),
            )
            selected = next(worker for worker in workers if worker.id == worker_id)
            with st.form("worker_edit"):
                row = st.columns(4)
                first = row[0].text_input("First name", selected.first_name)
                last = row[1].text_input("Last name", selected.last_name)
                email = row[2].text_input("Email", selected.email or "")
                phone = row[3].text_input("Phone", selected.phone or "")
                row = st.columns(3)
                role = row[0].text_input("Role", selected.role)
                hourly = row[1].number_input(
                    "Hourly cost", min_value=0.0, value=float(selected.hourly_cost)
                )
                status = row[2].selectbox(
                    "Employment",
                    list(EmploymentStatus),
                    index=list(EmploymentStatus).index(selected.employment_status),
                    format_func=lambda value: value.label,
                )
                skills = st.text_input("Skills", ", ".join(selected.skills))
                active = st.checkbox("Active", selected.is_active)
                submitted = st.form_submit_button("Save worker")
            if submitted:
                try:
                    payload = WorkerCreate(
                        business_id=business_id,
                        first_name=first,
                        last_name=last,
                        email=email or None,
                        phone=phone or None,
                        role=role,
                        hourly_cost=Decimal(str(hourly)),
                        employment_status=status,
                        skills=[item.strip() for item in skills.split(",") if item.strip()],
                        is_active=active,
                    )
                    with session_scope() as session:
                        WorkerService(session).update(worker_id, business_id, payload)
                    st.success("Worker updated.")
                    st.rerun()
                except ValidationError as exc:
                    st.error(str(exc))
