"""Lead lifecycle and transactional qualified-lead conversion."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Customer, Job, Lead
from app.database.models.enums import JobStatus, LeadStatus
from app.database.repositories import LeadRepository
from app.schemas.lead import LeadConversion, LeadCreate, LeadUpdate
from app.services.activity_service import record_activity
from app.utils.dates import utc_now
from app.utils.validation import DomainError

TRANSITIONS: dict[LeadStatus, set[LeadStatus]] = {
    LeadStatus.NEW: {LeadStatus.CONTACTED, LeadStatus.QUALIFIED, LeadStatus.LOST},
    LeadStatus.CONTACTED: {LeadStatus.QUALIFIED, LeadStatus.FOLLOW_UP, LeadStatus.LOST},
    LeadStatus.FOLLOW_UP: {LeadStatus.CONTACTED, LeadStatus.QUALIFIED, LeadStatus.LOST},
    LeadStatus.QUALIFIED: {LeadStatus.FOLLOW_UP, LeadStatus.LOST},
    LeadStatus.CONVERTED: set(),
    LeadStatus.LOST: set(),
}


class LeadService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = LeadRepository(session)

    def create(self, data: LeadCreate) -> Lead:
        if data.status != LeadStatus.NEW:
            raise DomainError("New leads must begin in the New stage.")
        lead = self.repository.add(Lead(**data.model_dump()))
        record_activity(self.session, lead.business_id, "lead", lead.id, "created", "Lead created")
        return lead

    def update(self, lead_id: int, business_id: int, data: LeadUpdate) -> Lead:
        lead = self.repository.require_for_business(lead_id, business_id)
        if data.business_id != business_id:
            raise DomainError("Lead business cannot be changed.")
        if data.status != lead.status:
            raise DomainError("Use the status action to move a lead through the pipeline.")
        values = data.model_dump(exclude={"business_id", "status", "lost_reason"})
        self.repository.update(lead, values)
        record_activity(
            self.session, business_id, "lead", lead.id, "updated", "Lead details updated"
        )
        return lead

    def transition(
        self,
        lead_id: int,
        business_id: int,
        status: LeadStatus,
        lost_reason: str | None = None,
    ) -> Lead:
        lead = self.repository.require_for_business(lead_id, business_id)
        if status == lead.status:
            return lead
        if status == LeadStatus.CONVERTED:
            raise DomainError("Use the conversion workflow to create the customer and job.")
        if status not in TRANSITIONS[lead.status]:
            raise DomainError(f"A {lead.status.label} lead cannot move directly to {status.label}.")
        if status == LeadStatus.LOST and not lost_reason:
            raise DomainError("A lost reason is required.")
        lead.status = status
        lead.lost_reason = lost_reason if status == LeadStatus.LOST else None
        record_activity(
            self.session,
            business_id,
            "lead",
            lead.id,
            "status_changed",
            f"Lead moved to {status.label}",
        )
        self.session.flush()
        return lead

    def convert(self, data: LeadConversion) -> tuple[Customer, Job]:
        """Create customer and job, then mark the qualified lead converted atomically."""
        lead = self.repository.require_for_business(data.lead_id, data.business_id)
        if lead.status == LeadStatus.CONVERTED or lead.converted_at is not None:
            raise DomainError("This lead has already been converted.")
        if lead.status != LeadStatus.QUALIFIED:
            raise DomainError("Only a qualified lead can be converted.")
        existing_job = self.session.scalar(select(Job).where(Job.originating_lead_id == lead.id))
        if existing_job is not None:
            raise DomainError("This lead already has an originating job.")

        customer = Customer(**data.customer.model_dump())
        self.session.add(customer)
        self.session.flush()

        job_values = data.job.model_dump()
        scheduled_start = job_values.get("scheduled_start")
        job = Job(
            **job_values,
            business_id=data.business_id,
            customer_id=customer.id,
            originating_lead_id=lead.id,
            status=JobStatus.SCHEDULED if scheduled_start else JobStatus.UNSCHEDULED,
        )
        self.session.add(job)
        self.session.flush()

        lead.status = LeadStatus.CONVERTED
        lead.converted_at = utc_now()
        record_activity(
            self.session,
            data.business_id,
            "customer",
            customer.id,
            "created_from_lead",
            "Customer created from qualified lead",
        )
        record_activity(
            self.session,
            data.business_id,
            "job",
            job.id,
            "created_from_lead",
            f"Job {job.job_number} created from qualified lead",
        )
        record_activity(
            self.session,
            data.business_id,
            "lead",
            lead.id,
            "converted",
            "Qualified lead converted to customer and job",
        )
        return customer, job
