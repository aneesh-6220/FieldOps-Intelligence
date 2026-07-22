"""Phase 1 relational model for lead-to-completed-job operations."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin
from app.database.models.enums import (
    CustomerStatus,
    EmploymentStatus,
    JobStatus,
    LeadSource,
    LeadStatus,
    PricingModel,
    Priority,
)

MoneyColumn = Numeric(12, 2)
RateColumn = Numeric(7, 4)


def enum_column(enum_type: type[Any]) -> Enum:
    """Persist stable lowercase enum values."""
    return Enum(
        enum_type,
        values_callable=lambda items: [item.value for item in items],
        native_enum=False,
    )


class Business(TimestampMixin, Base):
    __tablename__ = "businesses"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    industry: Mapped[str] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(40))
    city: Mapped[str | None] = mapped_column(String(100))
    province_or_state: Mapped[str | None] = mapped_column(String(100))
    country: Mapped[str] = mapped_column(String(80), default="Canada")
    currency_code: Mapped[str] = mapped_column(String(3), default="CAD")
    timezone: Mapped[str] = mapped_column(String(80), default="America/Toronto")
    default_tax_rate: Mapped[Decimal] = mapped_column(RateColumn, default=Decimal("0.13"))
    settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Service(TimestampMixin, Base):
    __tablename__ = "services"
    __table_args__ = (UniqueConstraint("business_id", "name", name="uq_service_business_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    pricing_model: Mapped[PricingModel] = mapped_column(enum_column(PricingModel))
    base_price: Mapped[Decimal] = mapped_column(MoneyColumn, default=Decimal("0"))
    estimated_duration_minutes: Mapped[int] = mapped_column(Integer, default=60)
    default_cost: Mapped[Decimal] = mapped_column(MoneyColumn, default=Decimal("0"))
    seasonal: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Worker(TimestampMixin, Base):
    __tablename__ = "workers"
    __table_args__ = (UniqueConstraint("business_id", "email", name="uq_worker_business_email"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id", ondelete="RESTRICT"), index=True
    )
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(40))
    role: Mapped[str] = mapped_column(String(100), default="Field technician")
    hourly_cost: Mapped[Decimal] = mapped_column(MoneyColumn, default=Decimal("0"))
    employment_status: Mapped[EmploymentStatus] = mapped_column(enum_column(EmploymentStatus))
    skills: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    assignments: Mapped[list["JobAssignment"]] = relationship(back_populates="worker")

    @property
    def display_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


class Customer(TimestampMixin, Base):
    __tablename__ = "customers"
    __table_args__ = (Index("ix_customer_business_status", "business_id", "customer_status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id", ondelete="RESTRICT"), index=True
    )
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100), default="")
    company_name: Mapped[str | None] = mapped_column(String(160))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(40))
    street_address: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(100))
    province_or_state: Mapped[str | None] = mapped_column(String(100))
    postal_code: Mapped[str | None] = mapped_column(String(20))
    acquisition_source: Mapped[LeadSource | None] = mapped_column(enum_column(LeadSource))
    notes: Mapped[str | None] = mapped_column(Text)
    customer_status: Mapped[CustomerStatus] = mapped_column(
        enum_column(CustomerStatus), default=CustomerStatus.ACTIVE
    )
    jobs: Mapped[list["Job"]] = relationship(back_populates="customer")

    @property
    def display_name(self) -> str:
        return self.company_name or f"{self.first_name} {self.last_name}".strip()


class Lead(TimestampMixin, Base):
    __tablename__ = "leads"
    __table_args__ = (Index("ix_lead_business_status", "business_id", "status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id", ondelete="RESTRICT"), index=True
    )
    contact_name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(40))
    address: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(100))
    postal_code: Mapped[str | None] = mapped_column(String(20))
    service_id: Mapped[int | None] = mapped_column(ForeignKey("services.id", ondelete="SET NULL"))
    source: Mapped[LeadSource] = mapped_column(enum_column(LeadSource), default=LeadSource.OTHER)
    estimated_value: Mapped[Decimal] = mapped_column(MoneyColumn, default=Decimal("0"))
    status: Mapped[LeadStatus] = mapped_column(enum_column(LeadStatus), default=LeadStatus.NEW)
    priority: Mapped[Priority] = mapped_column(enum_column(Priority), default=Priority.MEDIUM)
    assigned_worker_id: Mapped[int | None] = mapped_column(
        ForeignKey("workers.id", ondelete="SET NULL")
    )
    next_follow_up_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    converted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lost_reason: Mapped[str | None] = mapped_column(String(255))
    service: Mapped[Service | None] = relationship()
    assigned_worker: Mapped[Worker | None] = relationship()
    jobs: Mapped[list["Job"]] = relationship(back_populates="originating_lead")


class Job(TimestampMixin, Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("business_id", "job_number", name="uq_job_business_number"),
        UniqueConstraint("originating_lead_id", name="uq_job_originating_lead"),
        Index("ix_job_business_status_schedule", "business_id", "status", "scheduled_start"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id", ondelete="RESTRICT"), index=True
    )
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="RESTRICT"))
    originating_lead_id: Mapped[int | None] = mapped_column(
        ForeignKey("leads.id", ondelete="SET NULL")
    )
    service_id: Mapped[int | None] = mapped_column(ForeignKey("services.id", ondelete="SET NULL"))
    job_number: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[JobStatus] = mapped_column(enum_column(JobStatus), default=JobStatus.UNSCHEDULED)
    priority: Mapped[Priority] = mapped_column(enum_column(Priority), default=Priority.MEDIUM)
    scheduled_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scheduled_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    street_address: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(100))
    postal_code: Mapped[str | None] = mapped_column(String(20))
    quoted_revenue: Mapped[Decimal] = mapped_column(MoneyColumn, default=Decimal("0"))
    final_revenue: Mapped[Decimal | None] = mapped_column(MoneyColumn)
    estimated_cost: Mapped[Decimal] = mapped_column(MoneyColumn, default=Decimal("0"))
    actual_cost: Mapped[Decimal | None] = mapped_column(MoneyColumn)
    notes: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    customer: Mapped[Customer] = relationship(back_populates="jobs")
    originating_lead: Mapped[Lead | None] = relationship(back_populates="jobs")
    service: Mapped[Service | None] = relationship()
    assignments: Mapped[list["JobAssignment"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class JobAssignment(Base):
    __tablename__ = "job_assignments"
    __table_args__ = (UniqueConstraint("job_id", "worker_id", name="uq_job_assignment"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    worker_id: Mapped[int] = mapped_column(
        ForeignKey("workers.id", ondelete="RESTRICT"), index=True
    )
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expected_hours: Mapped[Decimal] = mapped_column(Numeric(7, 2), default=Decimal("0"))
    actual_hours: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    labour_cost: Mapped[Decimal] = mapped_column(MoneyColumn, default=Decimal("0"))
    job: Mapped[Job] = relationship(back_populates="assignments")
    worker: Mapped[Worker] = relationship(back_populates="assignments")


class ActivityLog(Base):
    __tablename__ = "activity_logs"
    __table_args__ = (Index("ix_activity_business_created", "business_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id", ondelete="RESTRICT"), index=True
    )
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
