"""Phase 1 seed, analytics, insights, and export integration tests."""

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import ActivityLog, Customer, Job, Lead, Service, Worker
from app.database.models.enums import JobStatus
from app.database.seed import demo_anchor_date, seed_demo_data
from app.services.analytics_service import AnalyticsService
from app.services.export_service import export_csv
from app.services.insight_service import InsightService


def test_seed_counts_and_idempotency(session: Session) -> None:
    first = seed_demo_data(session)
    second = seed_demo_data(session)
    assert first.id == second.id
    assert session.scalar(select(func.count(Lead.id))) == 55
    assert session.scalar(select(func.count(Customer.id))) == 25
    assert session.scalar(select(func.count(Service.id))) == 8
    assert session.scalar(select(func.count(Worker.id))) == 4
    assert session.scalar(select(func.count(Job.id))) == 40
    assert session.scalar(select(func.count(ActivityLog.id))) >= 70


def test_seeded_analytics_are_reproducible(session: Session) -> None:
    business = seed_demo_data(session)
    first = AnalyticsService(session).snapshot(business.id)
    second = AnalyticsService(session).snapshot(business.id)
    assert first.kpis == second.kpis
    assert first.kpis["total_leads"] == 55
    assert first.kpis["total_jobs"] == 40
    assert first.kpis["realized_revenue"] > 0
    assert first.kpis["schedule_conflicts"] >= 1


def test_seeded_operational_insights_cover_phase_one_rules(session: Session) -> None:
    business = seed_demo_data(session)
    titles = {item.title for item in InsightService(session).generate(business.id)}
    assert "Lead follow-ups are overdue" in titles
    assert "Qualified leads are waiting for conversion" in titles
    assert "Scheduled jobs have no assigned workers" in titles
    assert "Worker assignments overlap" in titles
    assert "Past scheduled jobs remain incomplete" in titles
    assert "Completed jobs are missing final revenue" in titles
    assert "Actual job costs exceeded estimates" in titles
    assert "Jobs took longer than scheduled" in titles
    assert "Revenue depends heavily on one customer" in titles


def test_demo_scenario_keeps_upcoming_work_ahead_of_the_run_date(session: Session) -> None:
    """The demo must still show forward-looking work whenever it is reseeded."""
    seed_demo_data(session)
    today = demo_anchor_date()
    upcoming_unstaffed = [
        job
        for job in session.scalars(select(Job)).all()
        if job.status in {JobStatus.SCHEDULED, JobStatus.CONFIRMED}
        and job.scheduled_start is not None
        and job.scheduled_start.date() >= today
        and not job.assignments
    ]
    assert upcoming_unstaffed


def test_demo_records_are_identical_for_a_fixed_anchor(session: Session) -> None:
    """Only the calendar anchor moves; the dataset itself stays deterministic."""
    anchor = date(2026, 7, 21)
    seed_demo_data(session, anchor_date=anchor)
    jobs = session.scalars(select(Job).order_by(Job.id)).all()
    assert [job.job_number for job in jobs][:3] == [
        "JOB-2025-0001",
        "JOB-2025-0002",
        "JOB-2025-0003",
    ]
    assert min(
        job.scheduled_start.date() for job in jobs if job.scheduled_start
    ) == anchor - timedelta(days=330)


def test_csv_export_is_business_scoped(session: Session) -> None:
    business = seed_demo_data(session)
    payload = export_csv(session, "leads", business.id).decode("utf-8")
    assert "contact_name" in payload.splitlines()[0]
    assert len(payload.splitlines()) == 56
