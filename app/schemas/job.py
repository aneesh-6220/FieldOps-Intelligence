"""Job, schedule, assignment, and completion schemas."""

from datetime import datetime
from decimal import Decimal

from pydantic import Field, model_validator

from app.database.models.enums import JobStatus, Priority
from app.schemas.common import Schema


class JobCreate(Schema):
    business_id: int
    customer_id: int
    originating_lead_id: int | None = None
    service_id: int | None = None
    job_number: str = Field(min_length=2, max_length=40)
    title: str = Field(min_length=2, max_length=200)
    description: str | None = None
    status: JobStatus = JobStatus.UNSCHEDULED
    priority: Priority = Priority.MEDIUM
    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None
    street_address: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)
    quoted_revenue: Decimal = Field(default=Decimal("0"), ge=0)
    estimated_cost: Decimal = Field(default=Decimal("0"), ge=0)
    notes: str | None = None

    @model_validator(mode="after")
    def validate_schedule(self) -> "JobCreate":
        _validate_schedule(self.scheduled_start, self.scheduled_end, self.status)
        return self


class JobUpdate(JobCreate):
    """Full job edit payload."""


class ConversionJobCreate(Schema):
    """Job proposal used before the conversion creates a customer ID."""

    service_id: int | None = None
    job_number: str = Field(min_length=2, max_length=40)
    title: str = Field(min_length=2, max_length=200)
    description: str | None = None
    priority: Priority = Priority.MEDIUM
    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None
    street_address: str | None = None
    city: str | None = None
    postal_code: str | None = None
    quoted_revenue: Decimal = Field(default=Decimal("0"), ge=0)
    estimated_cost: Decimal = Field(default=Decimal("0"), ge=0)
    notes: str | None = None

    @model_validator(mode="after")
    def validate_times(self) -> "ConversionJobCreate":
        status = JobStatus.SCHEDULED if self.scheduled_start else JobStatus.UNSCHEDULED
        _validate_schedule(self.scheduled_start, self.scheduled_end, status)
        return self


class JobSchedule(Schema):
    scheduled_start: datetime
    scheduled_end: datetime

    @model_validator(mode="after")
    def validate_times(self) -> "JobSchedule":
        if self.scheduled_end <= self.scheduled_start:
            raise ValueError("Scheduled end must be after start")
        return self


class JobCompletion(Schema):
    actual_start: datetime
    actual_end: datetime
    final_revenue: Decimal = Field(ge=0)
    actual_cost: Decimal = Field(ge=0)

    @model_validator(mode="after")
    def validate_actual_times(self) -> "JobCompletion":
        if self.actual_end <= self.actual_start:
            raise ValueError("Actual end must be after start")
        return self


def _validate_schedule(start: datetime | None, end: datetime | None, status: JobStatus) -> None:
    if (start is None) != (end is None):
        raise ValueError("Scheduled start and end must be provided together")
    if start is not None and end is not None and end <= start:
        raise ValueError("Scheduled end must be after start")
    if status in {JobStatus.SCHEDULED, JobStatus.CONFIRMED} and start is None:
        raise ValueError("Scheduled or confirmed jobs require start and end times")
