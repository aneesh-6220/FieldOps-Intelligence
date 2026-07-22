"""Date helpers used by services and analytics."""

from datetime import UTC, date, datetime


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(UTC)


def start_of_month(value: date | datetime) -> date:
    """Return the first day of a date's month."""
    return date(value.year, value.month, 1)
