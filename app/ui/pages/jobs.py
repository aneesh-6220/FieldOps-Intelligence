"""Phase 1 job management from creation through completion."""

from datetime import date, datetime, time, timedelta
from decimal import Decimal

import streamlit as st
from pydantic import ValidationError
from sqlalchemy import func, select

from app.database.models import Customer, Job, Service, Worker
from app.database.models.enums import JobStatus, Priority
from app.database.repositories import JobRepository
from app.database.session import session_scope
from app.schemas.job import JobCompletion, JobCreate, JobSchedule, JobUpdate
from app.services.job_service import JOB_TRANSITIONS, JobService, ScheduleConflict
from app.ui.components.states import empty_state
from app.ui.formatting import currency, page_header
from app.utils.validation import DomainError


def render(business_id: int, currency_code: str) -> None:
    page_header(
        "Jobs",
        "Create, schedule, staff, update, and complete work with actual time and cost results.",
        "Work execution",
    )
    with session_scope() as session:
        customers = list(
            session.scalars(select(Customer).where(Customer.business_id == business_id)).all()
        )
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
        jobs = JobRepository(session).detailed(business_id)
        next_number = (
            session.scalar(select(func.count(Job.id)).where(Job.business_id == business_id)) or 0
        ) + 1
    customer_by_name = {customer.display_name: customer for customer in customers}
    service_by_name = {service.name: service for service in services}
    worker_by_name = {worker.display_name: worker for worker in workers}

    tabs = st.tabs(["Jobs", "Add", "Edit", "Schedule", "Team", "Status", "Complete", "Hours"])
    with tabs[0]:
        row = st.columns([1, 1.4])
        status_filter = row[0].multiselect(
            "Status", list(JobStatus), format_func=lambda value: value.label
        )
        search = row[1].text_input("Search job, title, or customer")
        shown = [
            job
            for job in jobs
            if (not status_filter or job.status in status_filter)
            and (
                not search
                or search.lower() in job.job_number.lower()
                or search.lower() in job.title.lower()
                or search.lower() in job.customer.display_name.lower()
            )
        ]
        if not shown:
            empty_state("No jobs match this view", "Adjust filters or create a job.")
        else:
            st.dataframe(
                [
                    {
                        "ID": job.id,
                        "Job": job.job_number,
                        "Customer": job.customer.display_name,
                        "Service": job.service.name if job.service else "Uncategorized",
                        "Status": job.status.label,
                        "Scheduled": job.scheduled_start,
                        "Team": ", ".join(
                            assignment.worker.display_name for assignment in job.assignments
                        )
                        or "Unassigned",
                        "Quoted": currency(job.quoted_revenue, currency_code),
                        "Final": currency(job.final_revenue, currency_code)
                        if job.final_revenue is not None
                        else "—",
                    }
                    for job in shown
                ],
                hide_index=True,
                use_container_width=True,
            )

    with tabs[1]:
        if not customers or not services:
            st.warning("Create a customer and active service before creating a job.")
        else:
            with st.form("job_create", clear_on_submit=True):
                row = st.columns(3)
                customer_name = row[0].selectbox("Customer", list(customer_by_name))
                service_name = row[1].selectbox("Service", list(service_by_name))
                job_number = row[2].text_input(
                    "Job number", f"JOB-{date.today().year}-{next_number:04d}"
                )
                row = st.columns(4)
                schedule_now = row[0].checkbox("Schedule now")
                job_date = row[1].date_input(
                    "Date", date.today() + timedelta(days=3), disabled=not schedule_now
                )
                start_time = row[2].time_input("Start", time(9), disabled=not schedule_now)
                duration = row[3].number_input(
                    "Hours", min_value=0.5, value=2.0, step=0.5, disabled=not schedule_now
                )
                row = st.columns(3)
                quoted = row[0].number_input(
                    "Quoted revenue",
                    min_value=0.0,
                    value=float(service_by_name[service_name].base_price),
                )
                estimated_cost = row[1].number_input(
                    "Estimated cost",
                    min_value=0.0,
                    value=float(service_by_name[service_name].default_cost),
                )
                priority = row[2].selectbox(
                    "Priority", list(Priority), index=1, format_func=lambda value: value.label
                )
                description = st.text_area("Description")
                submitted = st.form_submit_button("Create job", type="primary")
            if submitted:
                try:
                    customer = customer_by_name[customer_name]
                    service = service_by_name[service_name]
                    start = datetime.combine(job_date, start_time) if schedule_now else None
                    payload = JobCreate(
                        business_id=business_id,
                        customer_id=customer.id,
                        service_id=service.id,
                        job_number=job_number,
                        title=service.name,
                        description=description or None,
                        status=JobStatus.SCHEDULED if start else JobStatus.UNSCHEDULED,
                        priority=priority,
                        scheduled_start=start,
                        scheduled_end=start + timedelta(hours=duration) if start else None,
                        street_address=customer.street_address,
                        city=customer.city,
                        postal_code=customer.postal_code,
                        quoted_revenue=Decimal(str(quoted)),
                        estimated_cost=Decimal(str(estimated_cost)),
                    )
                    with session_scope() as session:
                        JobService(session).create(payload)
                    st.success("Job created.")
                    st.rerun()
                except (ValidationError, DomainError) as exc:
                    st.error(str(exc))

    with tabs[2]:
        editable = [
            job for job in jobs if job.status not in {JobStatus.COMPLETED, JobStatus.CANCELLED}
        ]
        if not editable:
            st.caption("No open jobs are available to edit.")
        else:
            job_id = st.selectbox(
                "Job to edit",
                [job.id for job in editable],
                format_func=lambda value: next(
                    f"{job.job_number} · {job.title}" for job in editable if job.id == value
                ),
                key="edit_job_id",
            )
            selected = next(job for job in editable if job.id == job_id)
            customer_names = list(customer_by_name)
            service_names = ["Uncategorized", *service_by_name]
            current_service = selected.service.name if selected.service else "Uncategorized"
            with st.form("job_edit"):
                row = st.columns(3)
                customer_name = row[0].selectbox(
                    "Customer",
                    customer_names,
                    index=customer_names.index(selected.customer.display_name),
                )
                service_name = row[1].selectbox(
                    "Service", service_names, index=service_names.index(current_service)
                )
                title = row[2].text_input("Title", selected.title)
                row = st.columns(4)
                job_number = row[0].text_input("Job number", selected.job_number)
                priority = row[1].selectbox(
                    "Priority",
                    list(Priority),
                    index=list(Priority).index(selected.priority),
                    format_func=lambda value: value.label,
                )
                quoted = row[2].number_input(
                    "Quoted revenue", min_value=0.0, value=float(selected.quoted_revenue)
                )
                estimated_cost = row[3].number_input(
                    "Estimated cost", min_value=0.0, value=float(selected.estimated_cost)
                )
                description = st.text_area("Description", selected.description or "")
                notes = st.text_area("Notes", selected.notes or "")
                submitted = st.form_submit_button("Save job")
            if submitted:
                try:
                    customer = customer_by_name[customer_name]
                    payload = JobUpdate(
                        business_id=business_id,
                        customer_id=customer.id,
                        originating_lead_id=selected.originating_lead_id,
                        service_id=service_by_name[service_name].id
                        if service_name in service_by_name
                        else None,
                        job_number=job_number,
                        title=title,
                        description=description or None,
                        status=selected.status,
                        priority=priority,
                        scheduled_start=selected.scheduled_start,
                        scheduled_end=selected.scheduled_end,
                        street_address=customer.street_address,
                        city=customer.city,
                        postal_code=customer.postal_code,
                        quoted_revenue=Decimal(str(quoted)),
                        estimated_cost=Decimal(str(estimated_cost)),
                        notes=notes or None,
                    )
                    with session_scope() as session:
                        JobService(session).update(job_id, business_id, payload)
                    st.success("Job updated.")
                    st.rerun()
                except (ValidationError, DomainError) as exc:
                    st.error(str(exc))

    with tabs[3]:
        schedulable = [
            job for job in jobs if job.status not in {JobStatus.COMPLETED, JobStatus.CANCELLED}
        ]
        if not schedulable:
            st.caption("No jobs are available to schedule.")
        else:
            job_id = st.selectbox(
                "Job",
                [job.id for job in schedulable],
                format_func=lambda value: next(
                    job.job_number for job in schedulable if job.id == value
                ),
                key="schedule_job_id",
            )
            selected = next(job for job in schedulable if job.id == job_id)
            row = st.columns(3)
            job_date = row[0].date_input(
                "Date",
                selected.scheduled_start.date() if selected.scheduled_start else date.today(),
            )
            start_time = row[1].time_input(
                "Start", selected.scheduled_start.time() if selected.scheduled_start else time(9)
            )
            duration = row[2].number_input(
                "Hours",
                min_value=0.5,
                value=(
                    (selected.scheduled_end - selected.scheduled_start).total_seconds() / 3600
                    if selected.scheduled_start and selected.scheduled_end
                    else 2.0
                ),
                step=0.5,
            )
            acknowledge = st.checkbox(
                "Proceed even if an assigned worker has an overlapping job.",
                key="schedule_ack",
            )
            if st.button("Save schedule"):
                try:
                    start = datetime.combine(job_date, start_time)
                    schedule_payload = JobSchedule(
                        scheduled_start=start,
                        scheduled_end=start + timedelta(hours=duration),
                    )
                    with session_scope() as session:
                        JobService(session).schedule(
                            job_id,
                            business_id,
                            schedule_payload,
                            acknowledge_conflicts=acknowledge,
                        )
                    st.success("Schedule saved.")
                    st.rerun()
                except (ValidationError, DomainError, ScheduleConflict) as exc:
                    st.error(str(exc))

    with tabs[4]:
        open_jobs = [
            job for job in jobs if job.status not in {JobStatus.COMPLETED, JobStatus.CANCELLED}
        ]
        if not open_jobs or not workers:
            st.caption("Open jobs and active workers are required.")
        else:
            job_id = st.selectbox(
                "Job",
                [job.id for job in open_jobs],
                format_func=lambda value: next(
                    job.job_number for job in open_jobs if job.id == value
                ),
                key="assignment_job_id",
            )
            worker_name = st.selectbox("Worker", list(worker_by_name))
            expected_hours = st.number_input("Expected hours", min_value=0.0, value=2.0, step=0.5)
            acknowledge = st.checkbox(
                "I acknowledge any displayed overlapping assignment and want to proceed.",
                key="assignment_ack",
            )
            if st.button("Assign worker"):
                try:
                    with session_scope() as session:
                        JobService(session).assign_worker(
                            job_id,
                            business_id,
                            worker_by_name[worker_name].id,
                            Decimal(str(expected_hours)),
                            acknowledge_conflict=acknowledge,
                        )
                    st.success("Worker assigned.")
                    st.rerun()
                except (DomainError, ScheduleConflict) as exc:
                    st.error(str(exc))

    with tabs[5]:
        mutable = [job for job in jobs if JOB_TRANSITIONS[job.status]]
        if not mutable:
            st.caption("No jobs have available status actions.")
        else:
            job_id = st.selectbox(
                "Job",
                [job.id for job in mutable],
                format_func=lambda value: next(
                    f"{job.job_number} · {job.status.label}" for job in mutable if job.id == value
                ),
                key="status_job_id",
            )
            selected = next(job for job in mutable if job.id == job_id)
            target = st.selectbox(
                "Move to",
                sorted(JOB_TRANSITIONS[selected.status], key=lambda value: value.value),
                format_func=lambda value: value.label,
            )
            if st.button("Update job status"):
                try:
                    with session_scope() as session:
                        JobService(session).transition(job_id, business_id, target)
                    st.success(f"Job moved to {target.label}.")
                    st.rerun()
                except DomainError as exc:
                    st.error(str(exc))

    with tabs[6]:
        completable = [
            job for job in jobs if job.status not in {JobStatus.COMPLETED, JobStatus.CANCELLED}
        ]
        if not completable:
            st.caption("No open jobs are available for completion.")
        else:
            job_id = st.selectbox(
                "Job",
                [job.id for job in completable],
                format_func=lambda value: next(
                    job.job_number for job in completable if job.id == value
                ),
                key="complete_job_id",
            )
            selected = next(job for job in completable if job.id == job_id)
            row = st.columns(3)
            work_date = row[0].date_input(
                "Work date",
                selected.scheduled_start.date() if selected.scheduled_start else date.today(),
            )
            actual_start = row[1].time_input("Actual start", time(9))
            actual_end = row[2].time_input("Actual end", time(11))
            row = st.columns(2)
            final_revenue = row[0].number_input(
                "Final revenue", min_value=0.0, value=float(selected.quoted_revenue)
            )
            actual_cost = row[1].number_input(
                "Actual cost", min_value=0.0, value=float(selected.estimated_cost)
            )
            if st.button("Complete job", type="primary"):
                try:
                    completion_payload = JobCompletion(
                        actual_start=datetime.combine(work_date, actual_start),
                        actual_end=datetime.combine(work_date, actual_end),
                        final_revenue=Decimal(str(final_revenue)),
                        actual_cost=Decimal(str(actual_cost)),
                    )
                    with session_scope() as session:
                        JobService(session).complete(job_id, business_id, completion_payload)
                    st.success("Job completed; actual results recorded.")
                    st.rerun()
                except (ValidationError, DomainError) as exc:
                    st.error(str(exc))

    with tabs[7]:
        assignments = [assignment for job in jobs for assignment in job.assignments]
        assignment_labels = {
            assignment.id: f"{job.job_number} · {assignment.worker.display_name}"
            for job in jobs
            for assignment in job.assignments
        }
        if not assignments:
            st.caption("No worker assignments exist.")
        else:
            assignment_id = st.selectbox(
                "Assignment",
                [item.id for item in assignments],
                format_func=lambda value: assignment_labels[value],
            )
            selected_assignment = next(item for item in assignments if item.id == assignment_id)
            actual_hours = st.number_input(
                "Actual hours",
                min_value=0.0,
                value=float(selected_assignment.actual_hours or selected_assignment.expected_hours),
                step=0.5,
            )
            if st.button("Save actual hours"):
                try:
                    with session_scope() as session:
                        JobService(session).record_assignment_hours(
                            assignment_id, business_id, Decimal(str(actual_hours))
                        )
                    st.success("Assignment hours updated.")
                    st.rerun()
                except DomainError as exc:
                    st.error(str(exc))
