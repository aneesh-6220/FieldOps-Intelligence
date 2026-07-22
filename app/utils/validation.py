"""Shared domain validation helpers."""

from datetime import datetime


class DomainError(ValueError):
    """User-correctable domain rule violation."""


def require_chronological(start: datetime | None, end: datetime | None, label: str) -> None:
    """Require end to follow start when both timestamps exist."""
    if start and end and end <= start:
        raise DomainError(f"{label} end time must be after its start time.")
