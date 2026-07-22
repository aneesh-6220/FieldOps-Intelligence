"""Audit-friendly operational activity recording."""

from sqlalchemy.orm import Session

from app.database.models import ActivityLog
from app.utils.dates import utc_now


def record_activity(
    session: Session,
    business_id: int,
    entity_type: str,
    entity_id: int,
    action: str,
    description: str,
) -> ActivityLog:
    """Record a significant domain action without storing sensitive payloads."""
    activity = ActivityLog(
        business_id=business_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        description=description,
        created_at=utc_now(),
    )
    session.add(activity)
    session.flush()
    return activity
