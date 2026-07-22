"""Typed deterministic operational insight output."""

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class Insight:
    category: str
    severity: Literal["informational", "attention", "important", "critical"]
    title: str
    explanation: str
    supporting_metric: str
    next_action: str
    page: str
    record_ids: list[int] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
