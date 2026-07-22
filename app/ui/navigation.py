"""Phase 1 page registry."""

from collections.abc import Callable

from app.ui.pages import (
    about,
    analytics,
    customers,
    exports,
    jobs,
    leads,
    overview,
    schedule,
    services,
    settings,
    team,
)

PageRenderer = Callable[[int, str], None]

PAGES: dict[str, PageRenderer] = {
    "Overview": overview.render,
    "Leads": leads.render,
    "Customers": customers.render,
    "Jobs": jobs.render,
    "Schedule": schedule.render,
    "Services": services.render,
    "Team": team.render,
    "Analytics": analytics.render,
    "Data Export": exports.render,
    "Settings": settings.render,
    "About": about.render,
}
