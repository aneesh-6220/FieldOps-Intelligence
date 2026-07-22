"""Weekly scheduling, backlog, and conflict visibility."""

from datetime import UTC, datetime, timedelta

import streamlit as st
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.analytics.anomalies import overlapping_assignments
from app.database.models import Job, JobAssignment, Service, Worker
from app.database.models.enums import JobStatus
from app.database.session import session_scope
from app.ui.components.states import empty_state
from app.ui.formatting import page_header


def _start(job: Job) -> datetime:
    if job.scheduled_start is None:
        raise ValueError("Scheduled job is missing a start time")
    return job.scheduled_start


def _end(job: Job) -> datetime:
    if job.scheduled_end is None:
        raise ValueError("Scheduled job is missing an end time")
    return job.scheduled_end


def render(business_id: int, currency_code: str) -> None:
    del currency_code
    page_header(
        "Schedule",
        "See upcoming work, staffing gaps, conflicts, and unscheduled backlog before they become dispatch problems.",
        "Delivery planning",
    )
    today = datetime.now(UTC).date()
    with session_scope() as session:
        jobs = list(
            session.scalars(
                select(Job)
                .options(
                    selectinload(Job.customer),
                    selectinload(Job.service),
                    selectinload(Job.assignments).selectinload(JobAssignment.worker),
                )
                .where(Job.business_id == business_id)
                .order_by(Job.scheduled_start)
            )
            .unique()
            .all()
        )
        services = list(
            session.scalars(select(Service).where(Service.business_id == business_id)).all()
        )
        workers = list(
            session.scalars(select(Worker).where(Worker.business_id == business_id)).all()
        )
    filters = st.columns(3)
    worker_filter = filters[0].selectbox(
        "Worker", ["All", *[worker.display_name for worker in workers]]
    )
    service_filter = filters[1].selectbox(
        "Service", ["All", *[service.name for service in services]]
    )
    status_filter = filters[2].multiselect(
        "Status",
        list(JobStatus),
        format_func=lambda value: value.label,
        default=[JobStatus.SCHEDULED, JobStatus.CONFIRMED, JobStatus.IN_PROGRESS],
    )
    scheduled = [
        job
        for job in jobs
        if job.scheduled_start
        and (not status_filter or job.status in status_filter)
        and (service_filter == "All" or (job.service and job.service.name == service_filter))
        and (
            worker_filter == "All"
            or any(
                assignment.worker.display_name == worker_filter for assignment in job.assignments
            )
        )
    ]
    upcoming = [job for job in scheduled if _start(job).date() >= today]
    week_start = today - timedelta(days=today.weekday())
    week = [job for job in upcoming if _start(job).date() < week_start + timedelta(days=7)]
    st.subheader("This week")
    if not week:
        empty_state(
            "No scheduled work in this view", "Adjust filters or schedule an unscheduled job."
        )
    else:
        for day_offset in range(7):
            day = week_start + timedelta(days=day_offset)
            day_jobs = [job for job in week if _start(job).date() == day]
            if day_jobs:
                st.markdown(f"**{day:%A, %B %d}**")
                st.dataframe(
                    [
                        {
                            "Time": f"{_start(job):%I:%M %p}–{_end(job):%I:%M %p}"
                            if job.scheduled_end
                            else f"{_start(job):%I:%M %p}",
                            "Job": job.job_number,
                            "Customer": job.customer.display_name,
                            "Service": job.service.name if job.service else "—",
                            "Team": ", ".join(
                                assignment.worker.display_name for assignment in job.assignments
                            )
                            or "Unassigned",
                            "Status": job.status.label,
                        }
                        for job in day_jobs
                    ],
                    hide_index=True,
                    use_container_width=True,
                )
    rows = [
        (job.id, assignment.worker_id, _start(job), _end(job))
        for job in upcoming
        if job.scheduled_end
        for assignment in job.assignments
    ]
    conflicts = overlapping_assignments(rows)
    unstaffed = [job for job in upcoming if not job.assignments]
    invalid = [
        job
        for job in jobs
        if job.scheduled_start and job.scheduled_end and job.scheduled_end <= job.scheduled_start
    ]
    overdue = [
        job
        for job in jobs
        if job.scheduled_end
        and job.scheduled_end.date() < today
        and job.status not in {JobStatus.COMPLETED, JobStatus.CANCELLED}
    ]
    columns = st.columns(3)
    columns[0].metric("Staffing gaps", len(unstaffed), "Upcoming jobs without workers")
    columns[1].metric("Assignment conflicts", len(conflicts), "Overlapping worker schedules")
    columns[2].metric("Past due", len(overdue), "Past scheduled end, still open")
    if conflicts:
        st.error(
            "Schedule conflict detected: "
            + "; ".join(
                f"worker #{worker}, jobs #{first} and #{second}"
                for worker, first, second in conflicts
            )
        )
    if invalid:
        st.error(f"{len(invalid)} jobs have an end time that is not after the start time.")
    left, right = st.columns(2)
    with left:
        st.subheader("Unscheduled backlog")
        unscheduled = [job for job in jobs if job.status == JobStatus.UNSCHEDULED]
        if unscheduled:
            st.dataframe(
                [
                    {
                        "Job": job.job_number,
                        "Customer": job.customer.display_name,
                        "Service": job.service.name if job.service else "—",
                        "Priority": job.priority.label,
                    }
                    for job in unscheduled
                ],
                hide_index=True,
                use_container_width=True,
            )
        else:
            st.caption("No unscheduled jobs.")
    with right:
        st.subheader("Past due")
        if overdue:
            st.dataframe(
                [
                    {
                        "Job": job.job_number,
                        "Scheduled end": job.scheduled_end,
                        "Status": job.status.label,
                    }
                    for job in overdue
                ],
                hide_index=True,
                use_container_width=True,
            )
        else:
            st.caption("No past-due jobs.")
