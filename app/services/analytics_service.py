"""Authoritative Phase 1 analytics snapshots for dashboard, analytics, and export."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.analytics.anomalies import overlapping_assignments
from app.analytics.metrics import (
    average_known,
    average_money,
    conversion_rate,
    cost_variance_ratio,
    customer_concentration,
    duration_hours,
    duration_variance_ratio,
    elapsed_days,
    lead_age_days,
    median_money,
    repeat_customer_revenue,
    safe_rate,
)
from app.database.models import ActivityLog, Job, JobAssignment, Lead
from app.database.models.enums import JobStatus, LeadStatus
from app.utils.currency import money


@dataclass
class AnalyticsSnapshot:
    kpis: dict[str, Any]
    lead_statuses: pd.DataFrame
    job_statuses: pd.DataFrame
    monthly_revenue: pd.DataFrame
    revenue_by_service: pd.DataFrame
    revenue_by_customer: pd.DataFrame
    conversion_by_source: pd.DataFrame
    conversion_by_service: pd.DataFrame
    worker_metrics: pd.DataFrame
    upcoming_jobs: pd.DataFrame
    recent_activity: pd.DataFrame


class AnalyticsService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def snapshot(
        self,
        business_id: int,
        as_of: date | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> AnalyticsSnapshot:
        today = as_of or datetime.now(UTC).date()
        leads = list(
            self.session.scalars(
                select(Lead)
                .options(selectinload(Lead.service))
                .where(Lead.business_id == business_id)
            ).all()
        )
        jobs = list(
            self.session.scalars(
                select(Job)
                .options(
                    selectinload(Job.service),
                    selectinload(Job.customer),
                    selectinload(Job.assignments).selectinload(JobAssignment.worker),
                )
                .where(Job.business_id == business_id)
            )
            .unique()
            .all()
        )
        activities = list(
            self.session.scalars(
                select(ActivityLog)
                .where(ActivityLog.business_id == business_id)
                .order_by(ActivityLog.created_at.desc())
                .limit(20)
            ).all()
        )

        def in_window(value: datetime) -> bool:
            record_date = value.date()
            return (start_date is None or record_date >= start_date) and (
                end_date is None or record_date <= end_date
            )

        leads = [lead for lead in leads if in_window(lead.created_at)]
        jobs = [
            job
            for job in jobs
            if in_window(job.completed_at or job.scheduled_start or job.created_at)
        ]
        activities = [activity for activity in activities if in_window(activity.created_at)]

        completed = [job for job in jobs if job.status == JobStatus.COMPLETED]
        scheduled = [
            job for job in jobs if job.status in {JobStatus.SCHEDULED, JobStatus.CONFIRMED}
        ]
        month_start = today.replace(day=1)
        week_end = today + timedelta(days=7)
        open_leads = [
            lead for lead in leads if lead.status not in {LeadStatus.CONVERTED, LeadStatus.LOST}
        ]
        known_revenue_jobs = [job for job in completed if job.final_revenue is not None]
        revenue_by_customer_id: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
        for job in known_revenue_jobs:
            revenue_by_customer_id[job.customer_id] += job.final_revenue or Decimal("0")
        conflicts = overlapping_assignments(
            [
                (job.id, assignment.worker_id, job.scheduled_start, job.scheduled_end)
                for job in jobs
                if job.scheduled_start is not None
                and job.scheduled_end is not None
                and job.status not in {JobStatus.COMPLETED, JobStatus.CANCELLED}
                for assignment in job.assignments
            ]
        )
        conversion_days = [
            elapsed_days(lead.created_at, lead.converted_at)
            for lead in leads
            if lead.converted_at is not None
        ]
        kpis: dict[str, Any] = {
            "total_leads": len(leads),
            "active_leads": len(open_leads),
            "qualified_leads": sum(lead.status == LeadStatus.QUALIFIED for lead in leads),
            "converted_leads": sum(lead.status == LeadStatus.CONVERTED for lead in leads),
            "lost_leads": sum(lead.status == LeadStatus.LOST for lead in leads),
            "conversion_rate": conversion_rate(lead.status.value for lead in leads),
            "average_lead_age_days": average_known(
                lead_age_days(lead.created_at, today) for lead in open_leads
            ),
            "overdue_followups": sum(
                lead.next_follow_up_date is not None and lead.next_follow_up_date < today
                for lead in open_leads
            ),
            "average_conversion_days": average_known(conversion_days),
            "total_jobs": len(jobs),
            "completed_jobs": len(completed),
            "scheduled_jobs": len(scheduled),
            "cancelled_jobs": sum(job.status == JobStatus.CANCELLED for job in jobs),
            "completion_rate": safe_rate(len(completed), len(jobs)),
            "cancellation_rate": safe_rate(
                sum(job.status == JobStatus.CANCELLED for job in jobs), len(jobs)
            ),
            "average_quoted_value": average_money(job.quoted_revenue for job in jobs),
            "average_final_value": average_money(job.final_revenue for job in completed),
            "median_final_value": median_money(job.final_revenue for job in completed),
            "average_duration_hours": average_known(
                duration_hours(job.actual_start, job.actual_end) for job in completed
            ),
            "average_duration_variance": average_known(
                duration_variance_ratio(
                    job.scheduled_start,
                    job.scheduled_end,
                    job.actual_start,
                    job.actual_end,
                )
                for job in completed
            ),
            "average_cost_variance": average_known(
                cost_variance_ratio(job.estimated_cost, job.actual_cost) for job in completed
            ),
            "quoted_revenue": money(sum((job.quoted_revenue for job in jobs), Decimal("0"))),
            "realized_revenue": money(
                sum((job.final_revenue or Decimal("0") for job in completed), Decimal("0"))
            ),
            "realized_monthly_revenue": money(
                sum(
                    (
                        job.final_revenue or Decimal("0")
                        for job in completed
                        if job.completed_at is not None and job.completed_at.date() >= month_start
                    ),
                    Decimal("0"),
                )
            ),
            "outstanding_quoted_value": money(
                sum(
                    (
                        job.quoted_revenue
                        for job in jobs
                        if job.status not in {JobStatus.COMPLETED, JobStatus.CANCELLED}
                    ),
                    Decimal("0"),
                )
            ),
            "average_completed_job_value": average_money(job.final_revenue for job in completed),
            "repeat_customer_revenue": repeat_customer_revenue(
                (job.customer_id, job.final_revenue) for job in known_revenue_jobs
            ),
            "top_customer_concentration": customer_concentration(revenue_by_customer_id),
            "jobs_scheduled_this_week": sum(
                job.scheduled_start is not None
                and today <= job.scheduled_start.date() <= week_end
                and job.status not in {JobStatus.COMPLETED, JobStatus.CANCELLED}
                for job in jobs
            ),
            "jobs_in_progress": sum(job.status == JobStatus.IN_PROGRESS for job in jobs),
            "completed_this_month": sum(
                job.completed_at is not None and job.completed_at.date() >= month_start
                for job in completed
            ),
            "schedule_conflicts": len(conflicts),
        }

        lead_status_counts: dict[str, int] = defaultdict(int)
        job_status_counts: dict[str, int] = defaultdict(int)
        monthly: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        service_revenue: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        customer_revenue: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        for lead in leads:
            lead_status_counts[lead.status.label] += 1
        for job in jobs:
            job_status_counts[job.status.label] += 1
            if job.completed_at is not None and job.final_revenue is not None:
                monthly[job.completed_at.strftime("%Y-%m")] += job.final_revenue
                service_revenue[job.service.name if job.service else "Uncategorized"] += (
                    job.final_revenue
                )
                customer_revenue[job.customer.display_name] += job.final_revenue

        def conversion_segments(kind: str) -> pd.DataFrame:
            groups: dict[str, list[Lead]] = defaultdict(list)
            for lead in leads:
                label = (
                    lead.source.label
                    if kind == "source"
                    else lead.service.name
                    if lead.service
                    else "Unassigned"
                )
                groups[label].append(lead)
            return pd.DataFrame(
                [
                    {
                        "segment": label,
                        "leads": len(values),
                        "converted": sum(item.status == LeadStatus.CONVERTED for item in values),
                        "conversion_rate": conversion_rate(item.status.value for item in values),
                        "low_sample": len(values) < 5,
                    }
                    for label, values in groups.items()
                ]
            )

        worker_rows: list[dict[str, Any]] = []
        workers: dict[int, dict[str, Any]] = {}
        for job in jobs:
            for assignment in job.assignments:
                record = workers.setdefault(
                    assignment.worker_id,
                    {
                        "worker": assignment.worker.display_name,
                        "assigned_jobs": 0,
                        "completed_jobs": 0,
                        "expected_hours": Decimal("0"),
                        "actual_hours": Decimal("0"),
                    },
                )
                record["assigned_jobs"] += 1
                record["completed_jobs"] += job.status == JobStatus.COMPLETED
                record["expected_hours"] += assignment.expected_hours
                record["actual_hours"] += assignment.actual_hours or Decimal("0")
        for worker_id, values in workers.items():
            values["worker_id"] = worker_id
            values["conflicts"] = sum(conflict[0] == worker_id for conflict in conflicts)
            values["expected_hours"] = float(values["expected_hours"])
            values["actual_hours"] = float(values["actual_hours"])
            worker_rows.append(values)

        upcoming = sorted(
            [
                job
                for job in jobs
                if job.scheduled_start is not None
                and job.scheduled_start.date() >= today
                and job.status not in {JobStatus.COMPLETED, JobStatus.CANCELLED}
            ],
            key=lambda job: job.scheduled_start or job.created_at,
        )[:10]
        return AnalyticsSnapshot(
            kpis=kpis,
            lead_statuses=pd.DataFrame(
                [{"status": key, "count": value} for key, value in lead_status_counts.items()]
            ),
            job_statuses=pd.DataFrame(
                [{"status": key, "count": value} for key, value in job_status_counts.items()]
            ),
            monthly_revenue=pd.DataFrame(
                [{"month": key, "revenue": float(value)} for key, value in sorted(monthly.items())]
            ),
            revenue_by_service=pd.DataFrame(
                [
                    {"service": key, "revenue": float(value)}
                    for key, value in service_revenue.items()
                ]
            ),
            revenue_by_customer=pd.DataFrame(
                [
                    {"customer": key, "revenue": float(value)}
                    for key, value in sorted(
                        customer_revenue.items(), key=lambda item: item[1], reverse=True
                    )
                ]
            ),
            conversion_by_source=conversion_segments("source"),
            conversion_by_service=conversion_segments("service"),
            worker_metrics=pd.DataFrame(worker_rows),
            upcoming_jobs=pd.DataFrame(
                [
                    {
                        "job": job.job_number,
                        "start": job.scheduled_start,
                        "customer": job.customer.display_name,
                        "service": job.service.name if job.service else "Uncategorized",
                        "team": ", ".join(
                            assignment.worker.display_name for assignment in job.assignments
                        )
                        or "Unassigned",
                        "status": job.status.label,
                    }
                    for job in upcoming
                ]
            ),
            recent_activity=pd.DataFrame(
                [
                    {
                        "when": activity.created_at,
                        "action": activity.action.replace("_", " ").title(),
                        "description": activity.description,
                    }
                    for activity in activities[:12]
                ]
            ),
        )

    def summary_csv(self, business_id: int) -> bytes:
        snapshot = self.snapshot(business_id)
        return (
            pd.DataFrame([{"metric": key, "value": value} for key, value in snapshot.kpis.items()])
            .to_csv(index=False)
            .encode("utf-8")
        )
