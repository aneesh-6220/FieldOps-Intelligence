"""Phase 1 operating overview."""

from datetime import UTC, datetime, timedelta

import plotly.express as px
import streamlit as st

from app.database.session import session_scope
from app.services.analytics_service import AnalyticsService
from app.ui.components.metrics import metric_card
from app.ui.components.states import empty_state
from app.ui.formatting import currency, page_header


def _rate(value: float | None) -> str:
    return f"{value:.1%}" if value is not None else "Not available"


def render(business_id: int, currency_code: str) -> None:
    page_header(
        "Overview",
        "The current sales pipeline, delivery workload, and realized results in one operating view.",
    )
    today = datetime.now(UTC).date()
    with st.expander("Date range", expanded=False):
        row = st.columns(2)
        start = row[0].date_input("From", today - timedelta(days=365))
        end = row[1].date_input("To", today + timedelta(days=30))
        if end < start:
            st.error("The end date must not be before the start date.")
            return
    with session_scope() as session:
        snapshot = AnalyticsService(session).snapshot(business_id, start_date=start, end_date=end)
    kpis = snapshot.kpis
    first = st.columns(5)
    first_cards = [
        ("Active leads", str(kpis["active_leads"]), "Open pipeline records"),
        ("Qualified leads", str(kpis["qualified_leads"]), "Ready for conversion review"),
        ("Overdue follow-ups", str(kpis["overdue_followups"]), "Open and past due"),
        ("Scheduled this week", str(kpis["jobs_scheduled_this_week"]), "Next seven days"),
        ("In progress", str(kpis["jobs_in_progress"]), "Work currently underway"),
    ]
    for column, card in zip(first, first_cards, strict=True):
        with column:
            metric_card(*card)
    second = st.columns(4)
    second_cards = [
        ("Completed this month", str(kpis["completed_this_month"]), "By completion date"),
        (
            "Realized this month",
            currency(kpis["realized_monthly_revenue"], currency_code),
            "Known final revenue",
        ),
        (
            "Outstanding quoted value",
            currency(kpis["outstanding_quoted_value"], currency_code),
            "Open non-cancelled jobs",
        ),
        (
            "Average completed job",
            currency(kpis["average_completed_job_value"], currency_code)
            if kpis["average_completed_job_value"] is not None
            else "Not available",
            "Completed jobs with final revenue",
        ),
    ]
    for column, card in zip(second, second_cards, strict=True):
        with column:
            metric_card(*card)

    left, right = st.columns(2)
    with left:
        st.subheader("Lead status")
        if snapshot.lead_statuses.empty:
            empty_state("No lead data", "Create a lead to begin measuring the pipeline.")
        else:
            figure = px.bar(
                snapshot.lead_statuses.sort_values("count"),
                x="count",
                y="status",
                orientation="h",
                color_discrete_sequence=["#17624b"],
            )
            figure.update_layout(height=300, margin=dict(l=0, r=10, t=10, b=0))
            st.plotly_chart(figure, use_container_width=True)
    with right:
        st.subheader("Jobs by status")
        if snapshot.job_statuses.empty:
            empty_state("No job data", "Create or convert a lead to create the first job.")
        else:
            figure = px.pie(
                snapshot.job_statuses,
                values="count",
                names="status",
                hole=0.58,
                color_discrete_sequence=px.colors.sequential.Teal,
            )
            figure.update_layout(height=300, margin=dict(l=0, r=10, t=10, b=0))
            st.plotly_chart(figure, use_container_width=True)
    left, right = st.columns([1.15, 1])
    with left:
        st.subheader("Monthly realized revenue")
        if snapshot.monthly_revenue.empty:
            empty_state(
                "No realized revenue", "Complete jobs with final revenue to build this trend."
            )
        else:
            figure = px.area(snapshot.monthly_revenue, x="month", y="revenue", markers=True)
            figure.update_traces(line_color="#17624b", fillcolor="rgba(23,98,75,.13)")
            figure.update_layout(
                height=310,
                margin=dict(l=0, r=10, t=10, b=0),
                yaxis_title=currency_code,
                xaxis_title=None,
            )
            st.plotly_chart(figure, use_container_width=True)
    with right:
        st.subheader("Revenue by service")
        if snapshot.revenue_by_service.empty:
            empty_state("No service revenue", "Completed jobs will populate this view.")
        else:
            figure = px.bar(
                snapshot.revenue_by_service.sort_values("revenue"),
                x="revenue",
                y="service",
                orientation="h",
                color_discrete_sequence=["#4f8b75"],
            )
            figure.update_layout(height=310, margin=dict(l=0, r=10, t=10, b=0))
            st.plotly_chart(figure, use_container_width=True)
    left, right = st.columns([1.3, 1])
    with left:
        st.subheader("Upcoming jobs")
        if snapshot.upcoming_jobs.empty:
            empty_state("No upcoming jobs", "Schedule an open job to place it here.")
        else:
            st.dataframe(snapshot.upcoming_jobs, hide_index=True, use_container_width=True)
    with right:
        st.subheader("Recent activity")
        if snapshot.recent_activity.empty:
            empty_state("No recent activity", "Workflow actions will be recorded here.")
        else:
            st.dataframe(snapshot.recent_activity, hide_index=True, use_container_width=True)
