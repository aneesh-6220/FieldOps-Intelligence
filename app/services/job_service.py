"""Job creation, scheduling, assignments, transitions, and completion."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Customer, Job, JobAssignment, Service, Worker
from app.database.models.enums import JobStatus
from app.database.repositories import JobRepository
from app.schemas.job import JobCompletion, JobCreate, JobSchedule, JobUpdate
from app.services.activity_service import record_activity
from app.utils.currency import money
from app.utils.dates import utc_now
from app.utils.validation import DomainError

JOB_TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
    JobStatus.UNSCHEDULED: {JobStatus.SCHEDULED, JobStatus.CANCELLED},
    JobStatus.SCHEDULED: {
        JobStatus.CONFIRMED,
        JobStatus.IN_PROGRESS,
        JobStatus.BLOCKED,
        JobStatus.CANCELLED,
    },
    JobStatus.CONFIRMED: {
        JobStatus.IN_PROGRESS,
        JobStatus.BLOCKED,
        JobStatus.CANCELLED,
    },
    JobStatus.IN_PROGRESS: {JobStatus.BLOCKED, JobStatus.CANCELLED},
    JobStatus.BLOCKED: {
        JobStatus.SCHEDULED,
        JobStatus.CONFIRMED,
        JobStatus.IN_PROGRESS,
        JobStatus.CANCELLED,
    },
    JobStatus.COMPLETED: set(),
    JobStatus.CANCELLED: set(),
}


class ScheduleConflict(DomainError):
    """A worker would be assigned to overlapping job intervals."""

    def __init__(self, worker_id: int, job_ids: list[int]) -> None:
        self.worker_id = worker_id
        self.job_ids = job_ids
        super().__init__(
            f"Worker #{worker_id} is already assigned to overlapping job(s): "
            + ", ".join(f"#{job_id}" for job_id in job_ids)
        )


class JobService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = JobRepository(session)

    def _validate_references(self, data: JobCreate | JobUpdate, business_id: int) -> None:
        customer = self.session.scalar(
            select(Customer).where(
                Customer.id == data.customer_id, Customer.business_id == business_id
            )
        )
        if customer is None:
            raise DomainError("Choose a customer from this business.")
        if data.service_id is not None:
            service = self.session.scalar(
                select(Service).where(
                    Service.id == data.service_id, Service.business_id == business_id
                )
            )
            if service is None:
                raise DomainError("Choose a service from this business.")

    def create(self, data: JobCreate) -> Job:
        self._validate_references(data, data.business_id)
        if data.status not in {JobStatus.UNSCHEDULED, JobStatus.SCHEDULED}:
            raise DomainError("New jobs must begin unscheduled or scheduled.")
        job = self.repository.add(Job(**data.model_dump()))
        record_activity(
            self.session,
            job.business_id,
            "job",
            job.id,
            "created",
            f"Job {job.job_number} created",
        )
        return job

    def update(self, job_id: int, business_id: int, data: JobUpdate) -> Job:
        job = self.repository.require_for_business(job_id, business_id)
        if data.business_id != business_id:
            raise DomainError("Job business cannot be changed.")
        if data.status != job.status:
            raise DomainError("Use job status actions to change lifecycle state.")
        self._validate_references(data, business_id)
        self.repository.update(
            job,
            data.model_dump(exclude={"business_id", "originating_lead_id", "status"}),
        )
        record_activity(
            self.session, business_id, "job", job.id, "updated", f"Job {job.job_number} updated"
        )
        return job

    def find_conflicts(
        self, job_id: int, worker_id: int, schedule: JobSchedule | None = None
    ) -> list[int]:
        job = self.repository.require(job_id)
        start = schedule.scheduled_start if schedule else job.scheduled_start
        end = schedule.scheduled_end if schedule else job.scheduled_end
        if start is None or end is None:
            return []
        conflicts = self.session.scalars(
            select(Job)
            .join(JobAssignment)
            .where(
                JobAssignment.worker_id == worker_id,
                Job.id != job_id,
                Job.status.not_in([JobStatus.COMPLETED, JobStatus.CANCELLED]),
                Job.scheduled_start < end,
                Job.scheduled_end > start,
            )
        ).all()
        return [item.id for item in conflicts]

    def schedule(
        self,
        job_id: int,
        business_id: int,
        data: JobSchedule,
        *,
        acknowledge_conflicts: bool = False,
    ) -> Job:
        job = self.repository.require_for_business(job_id, business_id)
        if job.status in {JobStatus.COMPLETED, JobStatus.CANCELLED}:
            raise DomainError("Completed or cancelled jobs cannot be rescheduled.")
        for assignment in job.assignments:
            conflicts = self.find_conflicts(job.id, assignment.worker_id, data)
            if conflicts and not acknowledge_conflicts:
                raise ScheduleConflict(assignment.worker_id, conflicts)
        job.scheduled_start = data.scheduled_start
        job.scheduled_end = data.scheduled_end
        job.status = JobStatus.SCHEDULED
        record_activity(
            self.session,
            business_id,
            "job",
            job.id,
            "scheduled",
            f"Job {job.job_number} scheduled",
        )
        return job

    def assign_worker(
        self,
        job_id: int,
        business_id: int,
        worker_id: int,
        expected_hours: Decimal,
        *,
        acknowledge_conflict: bool = False,
    ) -> JobAssignment:
        if expected_hours < 0:
            raise DomainError("Expected hours cannot be negative.")
        job = self.repository.require_for_business(job_id, business_id)
        worker = self.session.scalar(
            select(Worker).where(
                Worker.id == worker_id,
                Worker.business_id == business_id,
                Worker.is_active,
            )
        )
        if worker is None:
            raise DomainError("Choose an active worker from this business.")
        duplicate = self.session.scalar(
            select(JobAssignment).where(
                JobAssignment.job_id == job_id, JobAssignment.worker_id == worker_id
            )
        )
        if duplicate is not None:
            raise DomainError("This worker is already assigned to the job.")
        conflicts = self.find_conflicts(job.id, worker_id)
        if conflicts and not acknowledge_conflict:
            raise ScheduleConflict(worker_id, conflicts)
        assignment = JobAssignment(
            job_id=job.id,
            worker_id=worker.id,
            assigned_at=utc_now(),
            expected_hours=expected_hours,
            labour_cost=money(expected_hours * worker.hourly_cost),
        )
        self.session.add(assignment)
        self.session.flush()
        record_activity(
            self.session,
            business_id,
            "job",
            job.id,
            "worker_assigned",
            f"Worker assigned to {job.job_number}",
        )
        return assignment

    def record_assignment_hours(
        self, assignment_id: int, business_id: int, actual_hours: Decimal
    ) -> JobAssignment:
        if actual_hours < 0:
            raise DomainError("Actual hours cannot be negative.")
        assignment = self.session.scalar(
            select(JobAssignment)
            .join(Job)
            .where(JobAssignment.id == assignment_id, Job.business_id == business_id)
        )
        if assignment is None:
            raise LookupError("Assignment was not found")
        assignment.actual_hours = actual_hours
        assignment.labour_cost = money(actual_hours * assignment.worker.hourly_cost)
        return assignment

    def transition(self, job_id: int, business_id: int, status: JobStatus) -> Job:
        job = self.repository.require_for_business(job_id, business_id)
        if status == job.status:
            return job
        if status == JobStatus.COMPLETED:
            raise DomainError("Use the completion workflow to record actual results.")
        if status not in JOB_TRANSITIONS[job.status]:
            raise DomainError(f"A {job.status.label} job cannot move directly to {status.label}.")
        job.status = status
        record_activity(
            self.session,
            business_id,
            "job",
            job.id,
            "status_changed",
            f"Job moved to {status.label}",
        )
        return job

    def complete(self, job_id: int, business_id: int, data: JobCompletion) -> Job:
        job = self.repository.require_for_business(job_id, business_id)
        if job.status in {JobStatus.COMPLETED, JobStatus.CANCELLED}:
            raise DomainError("Completed or cancelled jobs cannot be completed again.")
        job.actual_start = data.actual_start
        job.actual_end = data.actual_end
        job.final_revenue = money(data.final_revenue)
        job.actual_cost = money(data.actual_cost)
        job.completed_at = data.actual_end
        job.status = JobStatus.COMPLETED
        record_activity(
            self.session,
            business_id,
            "job",
            job.id,
            "completed",
            f"Job {job.job_number} completed",
        )
        return job
