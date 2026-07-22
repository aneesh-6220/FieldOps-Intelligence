"""Worker schemas."""

from decimal import Decimal

from pydantic import EmailStr, Field

from app.database.models.enums import EmploymentStatus
from app.schemas.common import Schema


class WorkerCreate(Schema):
    business_id: int
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    role: str = Field(default="Field technician", max_length=100)
    hourly_cost: Decimal = Field(default=Decimal("0"), ge=0)
    employment_status: EmploymentStatus = EmploymentStatus.FULL_TIME
    skills: list[str] = Field(default_factory=list)
    is_active: bool = True
