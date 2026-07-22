"""Deterministic synthetic Phase 1 data for Summit Outdoor Services."""

import random
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.database.models import (
    ActivityLog,
    Business,
    Customer,
    Job,
    JobAssignment,
    Lead,
    Service,
    Worker,
)
from app.database.models.enums import (
    CustomerStatus,
    EmploymentStatus,
    JobStatus,
    LeadSource,
    LeadStatus,
    PricingModel,
    Priority,
)
from app.utils.currency import money

DEMO_SEED = 20250217
DEMO_DATE = date(2026, 7, 21)

FIRST_NAMES = [
    "Alex",
    "Maya",
    "Jordan",
    "Sofia",
    "Liam",
    "Priya",
    "Noah",
    "Emma",
    "Ethan",
    "Ava",
    "Lucas",
    "Zoe",
    "Owen",
    "Leah",
    "Isaac",
    "Nina",
    "Caleb",
    "Amara",
    "Leo",
    "Grace",
]
LAST_NAMES = [
    "Chen",
    "Patel",
    "Martin",
    "Singh",
    "Wilson",
    "Brown",
    "Roy",
    "Campbell",
    "Taylor",
    "Moore",
    "Clark",
    "Hall",
    "Lewis",
    "Young",
    "King",
    "Scott",
    "Green",
    "Adams",
    "Baker",
    "Hill",
]
CITIES = ["Oakville", "Burlington", "Milton", "Mississauga"]


def _timestamp(day: date, hour: int = 12, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour=hour, minute=minute), tzinfo=UTC)


def seed_demo_data(session: Session, *, force: bool = False) -> Business:
    """Seed an idempotent fixed-randomness dataset with intentional operating exceptions."""
    existing = session.scalar(select(Business).where(Business.name == "Summit Outdoor Services"))
    if existing and not force:
        return existing
    if existing and force:
        raise ValueError("Use the reset script before force-seeding an existing database")

    rng = random.Random(DEMO_SEED)
    business = Business(
        name="Summit Outdoor Services",
        industry="Landscaping and seasonal maintenance",
        email="demo@example.com",
        phone="555-0100",
        city="Oakville",
        province_or_state="Ontario",
        country="Canada",
        currency_code="CAD",
        timezone="America/Toronto",
        default_tax_rate=Decimal("0.13"),
        settings={
            "demo_data": True,
            "stale_lead_days": 14,
            "cost_overrun_threshold": 0.20,
            "duration_overrun_threshold": 0.25,
            "concentration_threshold": 0.60,
            "low_sample_threshold": 5,
        },
    )
    session.add(business)
    session.flush()

    service_specs = [
        ("Lawn Mowing", "Recurring care", 70, 32, 75, True),
        ("Garden Maintenance", "Property care", 150, 74, 120, True),
        ("Seasonal Cleanup", "Cleanup", 410, 220, 240, True),
        ("Snow Removal", "Winter services", 130, 65, 90, True),
        ("Hedge Trimming", "Property care", 225, 120, 150, True),
        ("Yard Waste Removal", "Cleanup", 185, 102, 90, False),
        ("Pressure Washing", "Exterior cleaning", 345, 175, 180, False),
        ("Property Maintenance Visit", "General maintenance", 165, 80, 120, False),
    ]
    services: list[Service] = []
    for name, category, price, cost, minutes, seasonal in service_specs:
        service = Service(
            business_id=business.id,
            name=name,
            category=category,
            description=f"Synthetic demo configuration for {name.lower()}.",
            pricing_model=PricingModel.FIXED,
            base_price=money(price),
            estimated_duration_minutes=minutes,
            default_cost=money(cost),
            seasonal=seasonal,
            is_active=True,
        )
        session.add(service)
        services.append(service)

    workers: list[Worker] = []
    for first, last, role, hourly, worker_status, skills in [
        ("Marcus", "Lee", "Crew lead", 31, EmploymentStatus.FULL_TIME, ["cleanup", "snow"]),
        (
            "Elena",
            "Garcia",
            "Field technician",
            25,
            EmploymentStatus.FULL_TIME,
            ["gardens", "hedges"],
        ),
        (
            "Sam",
            "Okafor",
            "Field technician",
            24,
            EmploymentStatus.FULL_TIME,
            ["mowing", "washing"],
        ),
        (
            "Taylor",
            "Nguyen",
            "Seasonal technician",
            22,
            EmploymentStatus.PART_TIME,
            ["cleanup", "snow"],
        ),
    ]:
        worker = Worker(
            business_id=business.id,
            first_name=first,
            last_name=last,
            email=f"{first.lower()}@example.com",
            phone=f"555-01{rng.randrange(10, 99)}",
            role=role,
            hourly_cost=money(hourly),
            employment_status=worker_status,
            skills=skills,
            is_active=True,
        )
        session.add(worker)
        workers.append(worker)
    session.flush()

    customers: list[Customer] = []
    sources = list(LeadSource)
    for index in range(25):
        customer = Customer(
            business_id=business.id,
            first_name=FIRST_NAMES[index % len(FIRST_NAMES)],
            last_name=LAST_NAMES[(index * 3) % len(LAST_NAMES)],
            company_name=(
                f"{LAST_NAMES[index % len(LAST_NAMES)]} Property Group"
                if index in {6, 17, 24}
                else None
            ),
            email=f"customer{index + 1}@example.com",
            phone=f"555-1{index:03d}",
            street_address=f"{110 + index * 7} Sample Street",
            city=CITIES[index % len(CITIES)],
            province_or_state="Ontario",
            postal_code=f"L{index % 9}L {index % 9}A{(index * 3) % 9}",
            acquisition_source=sources[index % len(sources)],
            notes="Synthetic demo customer.",
            customer_status=CustomerStatus.ACTIVE if index < 23 else CustomerStatus.INACTIVE,
            created_at=_timestamp(DEMO_DATE - timedelta(days=330 - index * 7)),
            updated_at=_timestamp(DEMO_DATE - timedelta(days=index % 20)),
        )
        session.add(customer)
        customers.append(customer)
    session.flush()

    leads: list[Lead] = []
    for index in range(55):
        created_day = DEMO_DATE - timedelta(days=350 - index * 6)
        if index < 22:
            lead_status = LeadStatus.CONVERTED
        elif index < 30:
            lead_status = LeadStatus.QUALIFIED
        elif index < 35:
            lead_status = LeadStatus.LOST
        elif index < 43:
            lead_status = LeadStatus.FOLLOW_UP
        elif index < 48:
            lead_status = LeadStatus.CONTACTED
        else:
            lead_status = LeadStatus.NEW
        service = services[(index * 3) % len(services)]
        linked_customer = customers[index] if index < 22 else None
        lead = Lead(
            business_id=business.id,
            contact_name=(
                linked_customer.display_name
                if linked_customer
                else f"{FIRST_NAMES[(index + 5) % 20]} {LAST_NAMES[(index + 9) % 20]}"
            ),
            email=linked_customer.email if linked_customer else f"lead{index + 1}@example.com",
            phone=linked_customer.phone if linked_customer else f"555-2{index:03d}",
            address=(
                linked_customer.street_address
                if linked_customer
                else f"{300 + index} Prospect Road"
            ),
            city=linked_customer.city if linked_customer else CITIES[(index + 1) % len(CITIES)],
            postal_code=linked_customer.postal_code if linked_customer else "L6J 1A1",
            service_id=service.id,
            source=sources[index % len(sources)],
            estimated_value=money(service.base_price * Decimal(str([1, 1, 1.5, 2][index % 4]))),
            status=lead_status,
            priority=[Priority.LOW, Priority.MEDIUM, Priority.HIGH, Priority.URGENT][index % 4],
            assigned_worker_id=workers[index % len(workers)].id if index % 3 else None,
            next_follow_up_date=(
                DEMO_DATE - timedelta(days=3 + index % 12)
                if lead_status in {LeadStatus.QUALIFIED, LeadStatus.FOLLOW_UP, LeadStatus.CONTACTED}
                else DEMO_DATE + timedelta(days=2 + index % 5)
                if lead_status == LeadStatus.NEW
                else None
            ),
            notes="Synthetic demo lead.",
            converted_at=(
                _timestamp(created_day + timedelta(days=5 + index % 12))
                if lead_status == LeadStatus.CONVERTED
                else None
            ),
            lost_reason=(
                ["Budget", "Timing", "Selected another provider"][index % 3]
                if lead_status == LeadStatus.LOST
                else None
            ),
            created_at=_timestamp(created_day),
            updated_at=_timestamp(min(DEMO_DATE, created_day + timedelta(days=15 + index % 20))),
        )
        session.add(lead)
        leads.append(lead)
    session.flush()

    jobs: list[Job] = []
    for index in range(40):
        if index < 28:
            scheduled_day = DEMO_DATE - timedelta(days=330 - index * 11)
            job_status = JobStatus.COMPLETED
        elif index < 30:
            scheduled_day = DEMO_DATE - timedelta(days=35 - index)
            job_status = JobStatus.CANCELLED
        elif index in {30, 31, 36, 37, 38}:
            scheduled_day = DEMO_DATE + timedelta(days=2 if index in {30, 31} else index - 33)
            job_status = JobStatus.SCHEDULED
        elif index == 32:
            scheduled_day = DEMO_DATE + timedelta(days=4)
            job_status = JobStatus.CONFIRMED
        elif index == 33:
            scheduled_day = DEMO_DATE - timedelta(days=1)
            job_status = JobStatus.IN_PROGRESS
        elif index in {34, 35}:
            scheduled_day = DEMO_DATE - timedelta(days=8 if index == 34 else -8)
            job_status = JobStatus.BLOCKED
        else:
            scheduled_day = DEMO_DATE + timedelta(days=14)
            job_status = JobStatus.UNSCHEDULED

        customer = customers[index if index < 22 else index % 10]
        service = services[(index * 3) % len(services)]
        start = (
            None
            if job_status == JobStatus.UNSCHEDULED
            else _timestamp(scheduled_day, 9 + index % 3)
        )
        if index == 31:
            start = _timestamp(DEMO_DATE + timedelta(days=2), 10)
        end = start + timedelta(minutes=service.estimated_duration_minutes) if start else None
        overrun = (
            Decimal("1.55") if index in {4, 12, 20} else Decimal(str(0.90 + (index % 5) * 0.05))
        )
        actual_start = (
            start + timedelta(minutes=index % 25)
            if job_status == JobStatus.COMPLETED and start
            else None
        )
        actual_end = (
            actual_start
            + timedelta(minutes=int(service.estimated_duration_minutes * float(overrun)))
            if actual_start
            else None
        )
        quoted = money(service.base_price * Decimal(str(1 + index % 3)))
        estimated_cost = money(service.default_cost * Decimal(str(1 + index % 2)))
        if index == 6:
            # Deliberate portfolio-sized contract used to demonstrate concentration risk.
            quoted = Decimal("25000.00")
            estimated_cost = Decimal("12500.00")
        actual_cost = money(estimated_cost * overrun) if job_status == JobStatus.COMPLETED else None
        final_revenue = (
            None
            if index == 7
            else money(quoted * Decimal(str(0.98 + (index % 4) * 0.02)))
            if job_status == JobStatus.COMPLETED
            else None
        )
        job = Job(
            business_id=business.id,
            customer_id=customer.id,
            originating_lead_id=leads[index].id if index < 22 else None,
            service_id=service.id,
            job_number=f"JOB-{scheduled_day.year}-{index + 1:04d}",
            title=service.name,
            description="Synthetic demo job.",
            status=job_status,
            priority=[Priority.LOW, Priority.MEDIUM, Priority.HIGH][index % 3],
            scheduled_start=start,
            scheduled_end=end,
            actual_start=actual_start,
            actual_end=actual_end,
            street_address=customer.street_address,
            city=customer.city,
            postal_code=customer.postal_code,
            quoted_revenue=quoted,
            final_revenue=final_revenue,
            estimated_cost=estimated_cost,
            actual_cost=actual_cost,
            notes=(
                "Synthetic multi-property portfolio contract."
                if index == 6
                else "Synthetic demo job."
            ),
            completed_at=actual_end if job_status == JobStatus.COMPLETED else None,
            created_at=_timestamp(scheduled_day - timedelta(days=8)),
            updated_at=actual_end or start or _timestamp(scheduled_day - timedelta(days=8)),
        )
        session.add(job)
        jobs.append(job)
    session.flush()

    for index, job in enumerate(jobs):
        if index not in {32, 36, 39}:
            worker = workers[0] if index in {30, 31} else workers[index % len(workers)]
            expected_hours = (
                Decimal(
                    str(round((job.scheduled_end - job.scheduled_start).total_seconds() / 3_600, 2))
                )
                if job.scheduled_start and job.scheduled_end
                else Decimal("0")
            )
            actual_hours = (
                Decimal(str(round((job.actual_end - job.actual_start).total_seconds() / 3_600, 2)))
                if job.actual_start and job.actual_end
                else None
            )
            session.add(
                JobAssignment(
                    job_id=job.id,
                    worker_id=worker.id,
                    assigned_at=job.created_at,
                    expected_hours=expected_hours,
                    actual_hours=actual_hours,
                    labour_cost=money((actual_hours or expected_hours) * worker.hourly_cost),
                )
            )

    for lead in leads:
        session.add(
            ActivityLog(
                business_id=business.id,
                entity_type="lead",
                entity_id=lead.id,
                action="converted" if lead.status == LeadStatus.CONVERTED else "created",
                description=f"Synthetic demo lead {lead.id} {lead.status.value}",
                created_at=lead.updated_at,
            )
        )
    for job in jobs[-20:]:
        session.add(
            ActivityLog(
                business_id=business.id,
                entity_type="job",
                entity_id=job.id,
                action="completed" if job.status == JobStatus.COMPLETED else "status_changed",
                description=f"Synthetic demo job {job.job_number} {job.status.value}",
                created_at=job.updated_at,
            )
        )
    session.flush()
    return business


def clear_database(session: Session) -> None:
    """Delete local records in foreign-key-safe order for the explicit reset command."""
    for model in [ActivityLog, JobAssignment, Job, Lead, Customer, Worker, Service, Business]:
        session.execute(delete(model))
