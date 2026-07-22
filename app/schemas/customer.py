"""Customer boundary schemas."""

from pydantic import EmailStr, Field, model_validator

from app.database.models.enums import CustomerStatus, LeadSource
from app.schemas.common import Schema


class CustomerCreate(Schema):
    business_id: int
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(default="", max_length=100)
    company_name: str | None = Field(default=None, max_length=160)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    street_address: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=100)
    province_or_state: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)
    acquisition_source: LeadSource | None = None
    notes: str | None = None
    customer_status: CustomerStatus = CustomerStatus.ACTIVE

    @model_validator(mode="after")
    def require_name(self) -> "CustomerCreate":
        if not self.first_name and not self.company_name:
            raise ValueError("A contact or company name is required")
        return self


class CustomerUpdate(CustomerCreate):
    """Full customer edit payload."""
