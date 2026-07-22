"""Lead-to-completed-job transactional workflow tests."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.models import ActivityLog, Customer, Job, Lead, Service, Worker
from app.database.models.enums import (
    CustomerStatus,
    EmploymentStatus,
    JobStatus,
    LeadSource,
    LeadStatus,
    PricingModel,
)
from app.database.repositories import LeadRepository
from app.schemas.customer import CustomerCreate
from app.schemas.job import ConversionJobCreate, JobCompletion, JobCreate, JobSchedule
from app.schemas.lead import LeadConversion, LeadCreate
from app.services.job_service import JobService, ScheduleConflict
from app.services.lead_service import LeadService
from app.utils.validation import DomainError


def _service(session: Session, business_id: int) -> Service:
    item = Service(
        business_id=business_id,
        name="Window Cleaning",
        category="Cleaning",
        pricing_model=PricingModel.FIXED,
        base_price=Decimal("200"),
        default_cost=Decimal("80"),
        estimated_duration_minutes=120,
        seasonal=False,
        is_active=True,
    )
    session.add(item)
    session.flush()
    return item


def _customer(session: Session, business_id: int, name: str = "Ari") -> Customer:
    item = Customer(
        business_id=business_id,
        first_name=name,
        last_name="Stone",
        customer_status=CustomerStatus.ACTIVE,
    )
    session.add(item)
    session.flush()
    return item


def _worker(session: Session, business_id: int) -> Worker:
    item = Worker(
        business_id=business_id,
        first_name="Lee",
        last_name="Worker",
        email="lee@example.com",
        hourly_cost=Decimal("25"),
        employment_status=EmploymentStatus.FULL_TIME,
        skills=[],
        is_active=True,
    )
    session.add(item)
    session.flush()
    return item


def _qualified_lead(session: Session, business_id: int, service_id: int) -> Lead:
    lead = LeadService(session).create(
        LeadCreate(
            business_id=business_id,
            contact_name="Jamie Rivera",
            email="jamie@example.com",
            source=LeadSource.REFERRAL,
            service_id=service_id,
            estimated_value=Decimal("500"),
        )
    )
    LeadService(session).transition(lead.id, business_id, LeadStatus.QUALIFIED)
    return lead


def _conversion(lead: Lead, business_id: int, service_id: int, number: str) -> LeadConversion:
    return LeadConversion(
        lead_id=lead.id,
        business_id=business_id,
        confirmed=True,
        customer=CustomerCreate(
            business_id=business_id,
            first_name="Jamie",
            last_name="Rivera",
            email="jamie@example.com",
            acquisition_source=LeadSource.REFERRAL,
        ),
        job=ConversionJobCreate(
            service_id=service_id,
            job_number=number,
            title="Window Cleaning",
            quoted_revenue=Decimal("500"),
            estimated_cost=Decimal("180"),
        ),
    )


def test_valid_lead_transitions(session: Session, business: object) -> None:
    lead = LeadService(session).create(
        LeadCreate(business_id=business.id, contact_name="Valid Lead")
    )
    LeadService(session).transition(lead.id, business.id, LeadStatus.CONTACTED)
    LeadService(session).transition(lead.id, business.id, LeadStatus.QUALIFIED)
    assert lead.status == LeadStatus.QUALIFIED


def test_invalid_lead_transition(session: Session, business: object) -> None:
    lead = LeadService(session).create(
        LeadCreate(business_id=business.id, contact_name="Invalid Lead")
    )
    with pytest.raises(DomainError):
        LeadService(session).transition(lead.id, business.id, LeadStatus.FOLLOW_UP)


def test_lost_lead_requires_reason(session: Session, business: object) -> None:
    lead = LeadService(session).create(
        LeadCreate(business_id=business.id, contact_name="Lost Lead")
    )
    with pytest.raises(DomainError):
        LeadService(session).transition(lead.id, business.id, LeadStatus.LOST)
    LeadService(session).transition(lead.id, business.id, LeadStatus.LOST, "Budget")
    assert lead.lost_reason == "Budget"


def test_conversion_requires_confirmation(session: Session, business: object) -> None:
    service = _service(session, business.id)
    lead = _qualified_lead(session, business.id, service.id)
    with pytest.raises(ValidationError):
        LeadConversion(
            **_conversion(lead, business.id, service.id, "JOB-1").model_dump(exclude={"confirmed"}),
            confirmed=False,
        )


def test_successful_conversion_creates_customer_job_and_activity(
    session: Session, business: object
) -> None:
    service = _service(session, business.id)
    lead = _qualified_lead(session, business.id, service.id)
    customer, job = LeadService(session).convert(
        _conversion(lead, business.id, service.id, "JOB-100")
    )
    assert customer.id is not None
    assert job.customer_id == customer.id
    assert job.originating_lead_id == lead.id
    assert lead.status == LeadStatus.CONVERTED
    assert lead.converted_at is not None
    assert session.scalar(select(func.count(ActivityLog.id))) >= 5


def test_duplicate_conversion_is_prevented(session: Session, business: object) -> None:
    service = _service(session, business.id)
    lead = _qualified_lead(session, business.id, service.id)
    LeadService(session).convert(_conversion(lead, business.id, service.id, "JOB-101"))
    with pytest.raises(DomainError):
        LeadService(session).convert(_conversion(lead, business.id, service.id, "JOB-102"))


def test_conversion_rolls_back_every_record_on_job_failure(
    session: Session, business: object
) -> None:
    service = _service(session, business.id)
    existing_customer = _customer(session, business.id)
    session.add(
        Job(
            business_id=business.id,
            customer_id=existing_customer.id,
            service_id=service.id,
            job_number="JOB-DUPLICATE",
            title="Existing",
            status=JobStatus.UNSCHEDULED,
            quoted_revenue=Decimal("0"),
            estimated_cost=Decimal("0"),
        )
    )
    lead = _qualified_lead(session, business.id, service.id)
    session.commit()
    customer_count = session.scalar(select(func.count(Customer.id)))
    with pytest.raises(IntegrityError):
        LeadService(session).convert(_conversion(lead, business.id, service.id, "JOB-DUPLICATE"))
    session.rollback()
    restored = session.get(Lead, lead.id)
    assert restored is not None and restored.status == LeadStatus.QUALIFIED
    assert restored.converted_at is None
    assert session.scalar(select(func.count(Customer.id))) == customer_count


def test_repository_is_business_scoped(session: Session, business: object) -> None:
    LeadService(session).create(LeadCreate(business_id=business.id, contact_name="Scoped Lead"))
    assert len(LeadRepository(session).pipeline(business.id)) == 1
    with pytest.raises(LookupError):
        LeadRepository(session).require_for_business(1, business.id + 99)


def test_manual_job_creation_and_schedule_validation(session: Session, business: object) -> None:
    service = _service(session, business.id)
    customer = _customer(session, business.id)
    job = JobService(session).create(
        JobCreate(
            business_id=business.id,
            customer_id=customer.id,
            service_id=service.id,
            job_number="JOB-MANUAL",
            title="Manual Job",
        )
    )
    assert job.status == JobStatus.UNSCHEDULED
    with pytest.raises(ValidationError):
        JobSchedule(
            scheduled_start=datetime(2026, 1, 1, 10),
            scheduled_end=datetime(2026, 1, 1, 9),
        )


def test_worker_assignment_and_duplicate_prevention(session: Session, business: object) -> None:
    service = _service(session, business.id)
    customer = _customer(session, business.id)
    worker = _worker(session, business.id)
    job = JobService(session).create(
        JobCreate(
            business_id=business.id,
            customer_id=customer.id,
            service_id=service.id,
            job_number="JOB-ASSIGN",
            title="Assign",
        )
    )
    assignment = JobService(session).assign_worker(job.id, business.id, worker.id, Decimal("2"))
    assert assignment.labour_cost == Decimal("50.00")
    with pytest.raises(DomainError):
        JobService(session).assign_worker(job.id, business.id, worker.id, Decimal("2"))


def test_schedule_conflict_requires_acknowledgement(session: Session, business: object) -> None:
    service = _service(session, business.id)
    customer = _customer(session, business.id)
    worker = _worker(session, business.id)
    start = datetime(2026, 5, 1, 9)
    jobs = []
    for index, offset in enumerate([0, 1]):
        job = JobService(session).create(
            JobCreate(
                business_id=business.id,
                customer_id=customer.id,
                service_id=service.id,
                job_number=f"JOB-CONFLICT-{index}",
                title="Conflict",
                status=JobStatus.SCHEDULED,
                scheduled_start=start + timedelta(hours=offset),
                scheduled_end=start + timedelta(hours=offset + 2),
            )
        )
        jobs.append(job)
    JobService(session).assign_worker(jobs[0].id, business.id, worker.id, Decimal("2"))
    with pytest.raises(ScheduleConflict):
        JobService(session).assign_worker(jobs[1].id, business.id, worker.id, Decimal("2"))
    assignment = JobService(session).assign_worker(
        jobs[1].id,
        business.id,
        worker.id,
        Decimal("2"),
        acknowledge_conflict=True,
    )
    assert assignment.id is not None


def test_completion_sets_timestamp_and_actuals(session: Session, business: object) -> None:
    service = _service(session, business.id)
    customer = _customer(session, business.id)
    job = JobService(session).create(
        JobCreate(
            business_id=business.id,
            customer_id=customer.id,
            service_id=service.id,
            job_number="JOB-COMPLETE",
            title="Complete",
        )
    )
    start = datetime.now(UTC) - timedelta(hours=2)
    completed = JobService(session).complete(
        job.id,
        business.id,
        JobCompletion(
            actual_start=start,
            actual_end=start + timedelta(hours=2),
            final_revenue=Decimal("210"),
            actual_cost=Decimal("95"),
        ),
    )
    assert completed.status == JobStatus.COMPLETED
    assert completed.completed_at == completed.actual_end
    assert completed.final_revenue == Decimal("210.00")


def test_negative_actual_hours_are_rejected(session: Session, business: object) -> None:
    service = _service(session, business.id)
    customer = _customer(session, business.id)
    worker = _worker(session, business.id)
    job = JobService(session).create(
        JobCreate(
            business_id=business.id,
            customer_id=customer.id,
            service_id=service.id,
            job_number="JOB-HOURS",
            title="Hours",
        )
    )
    assignment = JobService(session).assign_worker(job.id, business.id, worker.id, Decimal("2"))
    with pytest.raises(DomainError):
        JobService(session).record_assignment_hours(assignment.id, business.id, Decimal("-1"))
