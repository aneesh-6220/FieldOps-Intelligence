"""Deterministic Phase 1 operational insight rules."""

from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.analytics.anomalies import overlapping_assignments
from app.analytics.metrics import customer_concentration, duration_variance_ratio
from app.database.models import Business, Job, JobAssignment, Lead
from app.database.models.enums import JobStatus, LeadStatus
from app.schemas.analytics import Insight
from app.utils.currency import format_currency


class InsightService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def generate(self, business_id: int, currency: str = "CAD") -> list[Insight]:
        business = self.session.get(Business, business_id)
        thresholds = business.settings if business and business.settings else {}
        cost_threshold = Decimal(str(thresholds.get("cost_overrun_threshold", 0.20)))
        duration_threshold = float(thresholds.get("duration_overrun_threshold", 0.25))
        concentration_threshold = float(thresholds.get("concentration_threshold", 0.60))
        today = datetime.now(UTC).date()
        leads = list(
            self.session.scalars(select(Lead).where(Lead.business_id == business_id)).all()
        )
        jobs = list(
            self.session.scalars(
                select(Job)
                .options(
                    selectinload(Job.customer),
                    selectinload(Job.assignments).selectinload(JobAssignment.worker),
                )
                .where(Job.business_id == business_id)
            )
            .unique()
            .all()
        )
        insights: list[Insight] = []

        overdue = [
            lead
            for lead in leads
            if lead.next_follow_up_date is not None
            and lead.next_follow_up_date < today
            and lead.status not in {LeadStatus.CONVERTED, LeadStatus.LOST}
        ]
        if overdue:
            value = sum((lead.estimated_value for lead in overdue), Decimal("0"))
            insights.append(
                Insight(
                    category="Sales",
                    severity="important",
                    title="Lead follow-ups are overdue",
                    explanation=f"{len(overdue)} open leads worth {format_currency(value, currency)} have passed their follow-up dates. Delayed contact can reduce the chance of conversion.",
                    supporting_metric=f"{len(overdue)} overdue follow-ups",
                    next_action="Contact the oldest records first, then set a new date or close the lead.",
                    page="Leads",
                    record_ids=[lead.id for lead in overdue],
                )
            )

        qualified = [lead for lead in leads if lead.status == LeadStatus.QUALIFIED]
        if qualified:
            value = sum((lead.estimated_value for lead in qualified), Decimal("0"))
            insights.append(
                Insight(
                    category="Sales",
                    severity="attention",
                    title="Qualified leads are waiting for conversion",
                    explanation=f"{len(qualified)} qualified leads representing {format_currency(value, currency)} have no customer and job yet. They are ready for an explicit conversion decision.",
                    supporting_metric=f"{len(qualified)} qualified leads",
                    next_action="Review each proposal and convert the work that is ready to schedule.",
                    page="Leads",
                    record_ids=[lead.id for lead in qualified],
                )
            )

        unstaffed = [
            job
            for job in jobs
            if job.status in {JobStatus.SCHEDULED, JobStatus.CONFIRMED}
            and job.scheduled_start is not None
            and job.scheduled_start.date() >= today
            and not job.assignments
        ]
        if unstaffed:
            insights.append(
                Insight(
                    category="Scheduling",
                    severity="important",
                    title="Scheduled jobs have no assigned workers",
                    explanation=f"{len(unstaffed)} upcoming jobs cannot be dispatched because nobody is assigned.",
                    supporting_metric=f"{len(unstaffed)} unstaffed jobs",
                    next_action="Assign an available worker and review the conflict warning before confirming.",
                    page="Jobs",
                    record_ids=[job.id for job in unstaffed],
                )
            )

        conflict_rows = [
            (job.id, assignment.worker_id, job.scheduled_start, job.scheduled_end)
            for job in jobs
            if job.scheduled_start is not None
            and job.scheduled_end is not None
            and job.status not in {JobStatus.COMPLETED, JobStatus.CANCELLED}
            for assignment in job.assignments
        ]
        conflicts = overlapping_assignments(conflict_rows)
        if conflicts:
            job_ids = sorted({item for _, first, second in conflicts for item in (first, second)})
            insights.append(
                Insight(
                    category="Scheduling",
                    severity="critical",
                    title="Worker assignments overlap",
                    explanation=f"{len(conflicts)} assignment pairs place the same worker on overlapping jobs. This creates a dispatch commitment that cannot be met as scheduled.",
                    supporting_metric=f"{len(conflicts)} conflicts",
                    next_action="Move one job or assign a different worker before dispatch.",
                    page="Schedule",
                    record_ids=job_ids,
                )
            )

        overdue_jobs = [
            job
            for job in jobs
            if job.scheduled_end is not None
            and job.scheduled_end.date() < today
            and job.status not in {JobStatus.COMPLETED, JobStatus.CANCELLED}
        ]
        if overdue_jobs:
            insights.append(
                Insight(
                    category="Operations",
                    severity="important",
                    title="Past scheduled jobs remain incomplete",
                    explanation=f"{len(overdue_jobs)} jobs are past their scheduled end and still open. The operating record may no longer match field reality.",
                    supporting_metric=f"{len(overdue_jobs)} overdue jobs",
                    next_action="Confirm completion, reschedule, block, or cancel each job.",
                    page="Jobs",
                    record_ids=[job.id for job in overdue_jobs],
                )
            )

        missing_revenue = [
            job for job in jobs if job.status == JobStatus.COMPLETED and job.final_revenue is None
        ]
        if missing_revenue:
            insights.append(
                Insight(
                    category="Data Quality",
                    severity="important",
                    title="Completed jobs are missing final revenue",
                    explanation=f"{len(missing_revenue)} completed jobs have no final revenue, so realized-revenue metrics understate performance.",
                    supporting_metric=f"{len(missing_revenue)} incomplete financial records",
                    next_action="Enter the final revenue from the completed work record.",
                    page="Jobs",
                    record_ids=[job.id for job in missing_revenue],
                )
            )

        cost_overruns = [
            job
            for job in jobs
            if job.actual_cost is not None
            and job.estimated_cost > 0
            and job.actual_cost > job.estimated_cost * (Decimal("1") + cost_threshold)
        ]
        if cost_overruns:
            insights.append(
                Insight(
                    category="Operations",
                    severity="attention",
                    title="Actual job costs exceeded estimates",
                    explanation=f"{len(cost_overruns)} jobs exceeded estimated cost by more than {cost_threshold:.0%}. Repeated overruns can make otherwise healthy revenue misleading.",
                    supporting_metric=f"{len(cost_overruns)} cost overruns",
                    next_action="Review scope, labour time, and cost assumptions before pricing similar work.",
                    page="Analytics",
                    record_ids=[job.id for job in cost_overruns],
                )
            )

        duration_overruns = [
            job
            for job in jobs
            if (
                variance := duration_variance_ratio(
                    job.scheduled_start,
                    job.scheduled_end,
                    job.actual_start,
                    job.actual_end,
                )
            )
            is not None
            and variance > duration_threshold
        ]
        if duration_overruns:
            insights.append(
                Insight(
                    category="Operations",
                    severity="attention",
                    title="Jobs took longer than scheduled",
                    explanation=f"{len(duration_overruns)} jobs exceeded scheduled duration by more than {duration_threshold:.0%}. This can create downstream delays and staffing pressure.",
                    supporting_metric=f"{len(duration_overruns)} duration overruns",
                    next_action="Compare planned scope with actual hours and adjust future duration estimates.",
                    page="Analytics",
                    record_ids=[job.id for job in duration_overruns],
                )
            )

        revenue_by_customer: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
        for job in jobs:
            if job.status == JobStatus.COMPLETED and job.final_revenue is not None:
                revenue_by_customer[job.customer_id] += job.final_revenue
        concentration = customer_concentration(revenue_by_customer)
        if concentration is not None and concentration > concentration_threshold:
            insights.append(
                Insight(
                    category="Revenue",
                    severity="attention",
                    title="Revenue depends heavily on one customer",
                    explanation=f"The largest customer represents {concentration:.0%} of realized revenue, above the configured {concentration_threshold:.0%} threshold. Losing that account would materially affect results.",
                    supporting_metric=f"{concentration:.0%} largest-customer share",
                    next_action="Protect the relationship while developing additional customer revenue sources.",
                    page="Customers",
                )
            )

        severity_order = {"critical": 0, "important": 1, "attention": 2, "informational": 3}
        return sorted(insights, key=lambda item: severity_order[item.severity])
