"""Authoritative Phase 1 operational metric formulas."""

from collections import Counter
from collections.abc import Iterable
from datetime import UTC, date, datetime
from decimal import Decimal
from statistics import median

from app.utils.currency import money


def safe_rate(numerator: int | float | Decimal, denominator: int | float | Decimal) -> float | None:
    """Return a rate, or None when the denominator is zero."""
    return float(numerator) / float(denominator) if denominator else None


def conversion_rate(statuses: Iterable[str]) -> float | None:
    """Converted leads divided by all captured leads."""
    values = list(statuses)
    return safe_rate(sum(value == "converted" for value in values), len(values))


def average_money(values: Iterable[Decimal | None]) -> Decimal | None:
    """Mean of known money values; missing values are excluded."""
    known = [money(value) for value in values if value is not None]
    return money(sum(known, Decimal("0")) / len(known)) if known else None


def median_money(values: Iterable[Decimal | None]) -> Decimal | None:
    """Median of known money values; missing values are excluded."""
    known = [money(value) for value in values if value is not None]
    return money(median(known)) if known else None


def lead_age_days(created_at: datetime, as_of: date | None = None) -> int:
    """Whole calendar days since lead creation, never negative."""
    reference = as_of or datetime.now(UTC).date()
    return max(0, (reference - created_at.date()).days)


def elapsed_days(start: datetime, end: datetime) -> float:
    """Elapsed days between timestamps."""
    return max(0.0, (end - start).total_seconds() / 86_400)


def duration_hours(start: datetime | None, end: datetime | None) -> float | None:
    """Duration in hours, or None when timestamps are missing or invalid."""
    if start is None or end is None or end <= start:
        return None
    return (end - start).total_seconds() / 3_600


def duration_variance_ratio(
    scheduled_start: datetime | None,
    scheduled_end: datetime | None,
    actual_start: datetime | None,
    actual_end: datetime | None,
) -> float | None:
    """Actual duration divided by estimated duration minus one."""
    estimated = duration_hours(scheduled_start, scheduled_end)
    actual = duration_hours(actual_start, actual_end)
    if estimated is None or actual is None or estimated == 0:
        return None
    return actual / estimated - 1


def cost_variance_ratio(
    estimated_cost: Decimal | None, actual_cost: Decimal | None
) -> float | None:
    """Actual cost divided by estimated cost minus one."""
    if estimated_cost is None or actual_cost is None or estimated_cost <= 0:
        return None
    return float(actual_cost / estimated_cost - 1)


def repeat_customer_revenue(rows: Iterable[tuple[int, Decimal | None]]) -> Decimal:
    """Realized revenue from customers with at least two revenue-bearing jobs."""
    values = [(customer_id, value) for customer_id, value in rows if value is not None]
    counts = Counter(customer_id for customer_id, _ in values)
    return money(
        sum(
            (value for customer_id, value in values if counts[customer_id] >= 2),
            Decimal("0"),
        )
    )


def customer_concentration(revenue_by_customer: dict[int, Decimal]) -> float | None:
    """Largest customer's share of realized revenue."""
    total = sum(revenue_by_customer.values(), Decimal("0"))
    if total <= 0 or not revenue_by_customer:
        return None
    return float(max(revenue_by_customer.values()) / total)


def average_known(values: Iterable[int | float | None]) -> float | None:
    """Arithmetic mean of known numeric observations."""
    known = [value for value in values if value is not None]
    return sum(known) / len(known) if known else None
