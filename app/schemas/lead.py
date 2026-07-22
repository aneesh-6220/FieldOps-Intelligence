"""Lead creation, editing, transition, and conversion schemas."""

from datetime import date
from decimal import Decimal

from pydantic import EmailStr, Field, model_validator

from app.database.models.enums import LeadSource, LeadStatus, Priority
from app.schemas.common import Schema
from app.schemas.customer import CustomerCreate
from app.schemas.job import ConversionJobCreate


class LeadCreate(Schema):
    business_id: int
    contact_name: str = Field(min_length=2, max_length=160)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    address: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)
    service_id: int | None = None
    source: LeadSource = LeadSource.OTHER
    estimated_value: Decimal = Field(default=Decimal("0"), ge=0)
    status: LeadStatus = LeadStatus.NEW
    priority: Priority = Priority.MEDIUM
    assigned_worker_id: int | None = None
    next_follow_up_date: date | None = None
    notes: str | None = None
    lost_reason: str | None = None

    @model_validator(mode="after")
    def validate_loss_reason(self) -> "LeadCreate":
        if self.status == LeadStatus.LOST and not self.lost_reason:
            raise ValueError("A lost reason is required for lost leads")
        return self


class LeadUpdate(LeadCreate):
    """Full lead edit payload."""


class LeadStatusUpdate(Schema):
    status: LeadStatus
    lost_reason: str | None = None


class LeadConversion(Schema):
    lead_id: int
    business_id: int
    customer: CustomerCreate
    job: ConversionJobCreate
    confirmed: bool

    @model_validator(mode="after")
    def require_confirmation_and_matching_business(self) -> "LeadConversion":
        if not self.confirmed:
            raise ValueError("Conversion must be explicitly confirmed")
        if self.customer.business_id != self.business_id:
            raise ValueError("Customer business does not match conversion business")
        return self
