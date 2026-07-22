"""Schedule conflict detection tests."""

from datetime import datetime, timedelta

from app.analytics.anomalies import overlapping_assignments


def test_overlap_detects_same_worker_only() -> None:
    start = datetime(2026, 6, 1, 9)
    rows = [
        (10, 1, start, start + timedelta(hours=2)),
        (11, 1, start + timedelta(hours=1), start + timedelta(hours=3)),
        (12, 2, start + timedelta(hours=1), start + timedelta(hours=3)),
    ]
    assert overlapping_assignments(rows) == [(1, 10, 11)]


def test_touching_intervals_do_not_overlap() -> None:
    start = datetime(2026, 6, 1, 9)
    rows = [
        (10, 1, start, start + timedelta(hours=2)),
        (11, 1, start + timedelta(hours=2), start + timedelta(hours=3)),
    ]
    assert overlapping_assignments(rows) == []
