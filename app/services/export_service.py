"""Portable Phase 1 CSV exports."""

from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import Session

from app.database.models import Customer, Job, JobAssignment, Lead, Service, Worker

EXPORT_MODELS = {
    "leads": Lead,
    "customers": Customer,
    "jobs": Job,
    "job_assignments": JobAssignment,
    "workers": Worker,
    "services": Service,
}


def export_csv(session: Session, entity_name: str, business_id: int) -> bytes:
    """Export a clear, business-scoped CSV without mutating records."""
    model = EXPORT_MODELS[entity_name]
    rows: list[Any]
    if model is JobAssignment:
        rows = list(
            session.scalars(
                select(JobAssignment).join(Job).where(Job.business_id == business_id)
            ).all()
        )
    else:
        model_any: Any = model
        rows = list(
            session.scalars(select(model).where(model_any.business_id == business_id)).all()
        )
    columns = [column.key for column in inspect(model).columns]
    values = [{column: getattr(row, column) for column in columns} for row in rows]
    return pd.DataFrame(values, columns=columns).to_csv(index=False).encode("utf-8")
