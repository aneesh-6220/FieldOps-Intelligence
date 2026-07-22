"""Configurable service schemas."""

from decimal import Decimal

from pydantic import Field

from app.database.models.enums import PricingModel
from app.schemas.common import Schema


class ServiceCreate(Schema):
    business_id: int
    name: str = Field(min_length=2, max_length=160)
    category: str = Field(min_length=2, max_length=120)
    description: str | None = None
    pricing_model: PricingModel = PricingModel.FIXED
    base_price: Decimal = Field(default=Decimal("0"), ge=0)
    estimated_duration_minutes: int = Field(default=60, ge=1, le=10080)
    default_cost: Decimal = Field(default=Decimal("0"), ge=0)
    is_active: bool = True
    seasonal: bool = False
