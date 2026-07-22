"""Authoritative Phase 1 metric formula tests."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

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


def test_zero_denominator_is_unavailable() -> None:
    assert safe_rate(3, 0) is None


def test_conversion_rate() -> None:
    assert conversion_rate(["converted", "lost", "converted", "new"]) == 0.5


def test_empty_conversion_rate_is_unavailable() -> None:
    assert conversion_rate([]) is None


def test_average_and_median_money_ignore_missing() -> None:
    values = [Decimal("100"), Decimal("900"), Decimal("200"), None]
    assert average_money(values) == Decimal("400.00")
    assert median_money(values) == Decimal("200.00")


def test_money_aggregates_are_unavailable_without_known_values() -> None:
    assert average_money([None]) is None
    assert median_money([]) is None


def test_lead_age_and_conversion_elapsed_days() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2026, 1, 11, 12, tzinfo=UTC)
    assert lead_age_days(start, date(2026, 1, 16)) == 15
    assert elapsed_days(start, end) == 10.5


def test_duration_hours_rejects_missing_or_invalid_times() -> None:
    start = datetime(2026, 1, 1, 9)
    assert duration_hours(start, start + timedelta(hours=2)) == 2
    assert duration_hours(start, start) is None
    assert duration_hours(None, start) is None


def test_duration_variance() -> None:
    start = datetime(2026, 1, 1, 9)
    assert (
        duration_variance_ratio(
            start,
            start + timedelta(hours=2),
            start,
            start + timedelta(hours=3),
        )
        == 0.5
    )


def test_cost_variance() -> None:
    assert cost_variance_ratio(Decimal("100"), Decimal("125")) == 0.25
    assert cost_variance_ratio(Decimal("0"), Decimal("125")) is None
    assert cost_variance_ratio(Decimal("100"), None) is None


def test_repeat_customer_revenue() -> None:
    rows = [
        (1, Decimal("100")),
        (1, Decimal("200")),
        (2, Decimal("500")),
        (3, None),
    ]
    assert repeat_customer_revenue(rows) == Decimal("300.00")


def test_top_customer_concentration() -> None:
    values = {1: Decimal("70"), 2: Decimal("20"), 3: Decimal("10")}
    assert customer_concentration(values) == 0.7
    assert customer_concentration({}) is None


def test_average_known_excludes_missing() -> None:
    assert average_known([1.0, None, 3.0]) == 2.0
    assert average_known([]) is None
