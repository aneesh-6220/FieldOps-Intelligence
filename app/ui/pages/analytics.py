"""Defensible Phase 1 operating analytics and deterministic insights."""

import html

import plotly.express as px
import streamlit as st

from app.database.models import Business
from app.database.session import session_scope
from app.services.analytics_service import AnalyticsService
from app.services.insight_service import InsightService
from app.ui.components.states import empty_state
from app.ui.formatting import currency, page_header


def _rate(value: float | None) -> str:
    return f"{value:.1%}" if value is not None else "Not available"


def _number(value: float | None, suffix: str = "") -> str:
    return f"{value:.1f}{suffix}" if value is not None else "Not available"


def render(business_id: int, currency_code: str) -> None:
    page_header(
        "Analytics",
        "A limited set of reproducible lead, job, revenue, and worker measures with explicit low-data behavior.",
        "Operational performance",
    )
    with session_scope() as session:
        business = session.get(Business, business_id)
        low_sample = (
            int((business.settings or {}).get("low_sample_threshold", 5)) if business else 5
        )
        snapshot = AnalyticsService(session).snapshot(business_id)
        insights = InsightService(session).generate(business_id, currency_code)
    kpis = snapshot.kpis
    tabs = st.tabs(["Leads", "Jobs & revenue", "Team", "Operational insights"])
    with tabs[0]:
        row = st.columns(5)
        row[0].metric("Total leads", kpis["total_leads"])
        row[1].metric("Active", kpis["active_leads"])
        row[2].metric("Qualified", kpis["qualified_leads"])
        row[3].metric("Converted", kpis["converted_leads"])
        row[4].metric("Lost", kpis["lost_leads"])
        row = st.columns(4)
        row[0].metric("Conversion rate", _rate(kpis["conversion_rate"]))
        row[1].metric("Average open-lead age", _number(kpis["average_lead_age_days"], " days"))
        row[2].metric("Overdue follow-ups", kpis["overdue_followups"])
        row[3].metric(
            "Average time to conversion", _number(kpis["average_conversion_days"], " days")
        )
        left, right = st.columns(2)
        for column, title, frame in [
            (left, "Conversion by source", snapshot.conversion_by_source),
            (right, "Conversion by service", snapshot.conversion_by_service),
        ]:
            with column:
                st.subheader(title)
                if frame.empty:
                    empty_state("No segment data", "Lead records will populate this table.")
                else:
                    display = frame.copy()
                    display["warning"] = display.apply(
                        lambda row: (
                            f"Low sample (<{low_sample})" if row["leads"] < low_sample else ""
                        ),
                        axis=1,
                    )
                    st.dataframe(
                        display,
                        hide_index=True,
                        use_container_width=True,
                        column_config={
                            "conversion_rate": st.column_config.NumberColumn(format="percent")
                        },
                    )
        st.caption(
            "Conversion rate is converted leads divided by all leads in the segment. A zero denominator is shown as unavailable, not 0%."
        )

    with tabs[1]:
        row = st.columns(4)
        row[0].metric("Total jobs", kpis["total_jobs"])
        row[1].metric("Completed", kpis["completed_jobs"])
        row[2].metric("Scheduled / confirmed", kpis["scheduled_jobs"])
        row[3].metric("Cancelled", kpis["cancelled_jobs"])
        row = st.columns(4)
        row[0].metric("Completion rate", _rate(kpis["completion_rate"]))
        row[1].metric("Cancellation rate", _rate(kpis["cancellation_rate"]))
        row[2].metric("Average duration", _number(kpis["average_duration_hours"], " hr"))
        row[3].metric("Schedule conflicts", kpis["schedule_conflicts"])
        row = st.columns(4)
        row[0].metric(
            "Average quoted value",
            currency(kpis["average_quoted_value"], currency_code)
            if kpis["average_quoted_value"] is not None
            else "Not available",
        )
        row[1].metric(
            "Average final value",
            currency(kpis["average_final_value"], currency_code)
            if kpis["average_final_value"] is not None
            else "Not available",
        )
        row[2].metric(
            "Median final value",
            currency(kpis["median_final_value"], currency_code)
            if kpis["median_final_value"] is not None
            else "Not available",
        )
        row[3].metric("Realized revenue", currency(kpis["realized_revenue"], currency_code))
        row = st.columns(4)
        row[0].metric("Quoted revenue", currency(kpis["quoted_revenue"], currency_code))
        row[1].metric(
            "Repeat-customer revenue",
            currency(kpis["repeat_customer_revenue"], currency_code),
        )
        row[2].metric("Top-customer concentration", _rate(kpis["top_customer_concentration"]))
        row[3].metric("Average cost variance", _rate(kpis["average_cost_variance"]))
        st.metric("Average duration variance", _rate(kpis["average_duration_variance"]))
        left, right = st.columns(2)
        with left:
            st.subheader("Realized revenue by month")
            if snapshot.monthly_revenue.empty:
                empty_state("No realized revenue", "Complete jobs to build the trend.")
            else:
                figure = px.line(
                    snapshot.monthly_revenue,
                    x="month",
                    y="revenue",
                    markers=True,
                    color_discrete_sequence=["#17624b"],
                )
                figure.update_layout(height=320, margin=dict(l=0, r=10, t=10, b=0))
                st.plotly_chart(figure, use_container_width=True)
        with right:
            st.subheader("Realized revenue by service")
            if snapshot.revenue_by_service.empty:
                empty_state("No service revenue", "Complete jobs to populate this view.")
            else:
                figure = px.bar(
                    snapshot.revenue_by_service.sort_values("revenue"),
                    x="revenue",
                    y="service",
                    orientation="h",
                    color_discrete_sequence=["#4f8b75"],
                )
                figure.update_layout(height=320, margin=dict(l=0, r=10, t=10, b=0))
                st.plotly_chart(figure, use_container_width=True)
        st.subheader("Realized revenue by customer")
        st.dataframe(
            snapshot.revenue_by_customer,
            hide_index=True,
            use_container_width=True,
            column_config={"revenue": st.column_config.NumberColumn(format="$%.2f")},
        )
        st.caption(
            "Duration and cost variance are (actual ÷ estimate) − 1. Missing or nonpositive estimates are excluded."
        )

    with tabs[2]:
        if snapshot.worker_metrics.empty:
            empty_state("No assignment data", "Assign workers to jobs to populate this table.")
        else:
            st.dataframe(snapshot.worker_metrics, hide_index=True, use_container_width=True)
        st.caption(
            "Expected and actual hours come from job assignments. Conflict count is overlapping assignment pairs, not missed jobs."
        )

    with tabs[3]:
        if not insights:
            empty_state(
                "No active rule-based insights",
                "No current records meet a configured Phase 1 alert condition.",
            )
        for item in insights:
            st.markdown(
                f'<div class="insight {item.severity}"><div class="eyebrow">{html.escape(item.severity)} · {html.escape(item.category)}</div><h3>{html.escape(item.title)}</h3><p>{html.escape(item.explanation)}</p><p><b>Metric:</b> {html.escape(item.supporting_metric)}<br><b>Action:</b> {html.escape(item.next_action)}<br><b>Go to:</b> {html.escape(item.page)}</p></div>',
                unsafe_allow_html=True,
            )
        st.caption(
            "Insights use deterministic dates, workflow states, percentage thresholds, and schedule-overlap rules. No statistical anomaly model or language model is used."
        )
