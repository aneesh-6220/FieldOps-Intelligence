"""Business configuration schemas."""

from decimal import Decimal

from pydantic import EmailStr, Field, field_validator

from app.schemas.common import Schema


class BusinessUpdate(Schema):
    name: str = Field(min_length=2, max_length=160)
    industry: str = Field(min_length=2, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    city: str | None = Field(default=None, max_length=100)
    province_or_state: str | None = Field(default=None, max_length=100)
    country: str = Field(default="Canada", max_length=80)
    currency_code: str = Field(default="CAD", min_length=3, max_length=3)
    timezone: str = Field(default="America/Toronto", max_length=80)
    default_tax_rate: Decimal = Field(default=Decimal("0.13"), ge=0, le=1)

    @field_validator("currency_code")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class BusinessCreate(BusinessUpdate):
    """Minimum validated details for a blank operational workspace."""
