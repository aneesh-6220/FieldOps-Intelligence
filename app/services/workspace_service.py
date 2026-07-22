"""Initialization and isolation rules for operational and demo workspaces."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Business
from app.database.seed import clear_demo_database, seed_demo_data
from app.database.session import WorkspaceMode
from app.schemas.business import BusinessCreate
from app.utils.validation import DomainError

DEFAULT_WORKSPACE_SETTINGS = {
    "demo_data": False,
    "stale_lead_days": 14,
    "cost_overrun_threshold": 0.20,
    "duration_overrun_threshold": 0.25,
    "concentration_threshold": 0.60,
    "low_sample_threshold": 5,
}


class WorkspaceService:
    """Create and inspect one business in an already-selected physical database."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_business(self) -> Business | None:
        return self.session.scalar(select(Business).order_by(Business.id).limit(1))

    def create_operational_workspace(self, data: BusinessCreate) -> Business:
        if self.get_business() is not None:
            raise DomainError("This operational workspace has already been initialized.")
        business = Business(
            **data.model_dump(),
            settings=dict(DEFAULT_WORKSPACE_SETTINGS),
        )
        self.session.add(business)
        self.session.flush()
        return business

    def initialize_demo_workspace(self) -> Business:
        existing = self.get_business()
        if existing is not None and existing.settings.get("demo_data") is not True:
            raise DomainError("The demo database contains an operational workspace.")
        return seed_demo_data(self.session)

    def reset_demo_workspace(self) -> Business:
        clear_demo_database(self.session)
        return seed_demo_data(self.session)


def should_show_demo_banner(workspace: WorkspaceMode, business: Business) -> bool:
    """Require both the demo store and its explicit marker before showing demo UI."""
    return workspace == WorkspaceMode.DEMO and business.settings.get("demo_data") is True
