"""Deterministic schedule-overlap detection."""

from collections import defaultdict
from datetime import datetime


def overlapping_assignments(
    rows: list[tuple[int, int, datetime, datetime]],
) -> list[tuple[int, int, int]]:
    """Return worker ID and each pair of jobs with overlapping intervals."""
    by_worker: dict[int, list[tuple[int, datetime, datetime]]] = defaultdict(list)
    for job_id, worker_id, start, end in rows:
        by_worker[worker_id].append((job_id, start, end))
    conflicts: list[tuple[int, int, int]] = []
    for worker_id, assignments in by_worker.items():
        ordered = sorted(assignments, key=lambda value: value[1])
        for index, current in enumerate(ordered):
            for following in ordered[index + 1 :]:
                if following[1] >= current[2]:
                    break
                conflicts.append((worker_id, current[0], following[0]))
    return conflicts
