"""Phase 1 repositories with tenant-scoped query shapes."""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database.models import Customer, Job, JobAssignment, Lead, Service, Worker
from app.database.repositories.base import BusinessRepository


class LeadRepository(BusinessRepository[Lead]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Lead)

    def pipeline(self, business_id: int) -> list[Lead]:
        return list(
            self.session.scalars(
                select(Lead)
                .options(selectinload(Lead.service), selectinload(Lead.assigned_worker))
                .where(Lead.business_id == business_id)
                .order_by(Lead.created_at.desc())
            ).all()
        )


class CustomerRepository(BusinessRepository[Customer]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Customer)

    def with_history(self, customer_id: int, business_id: int) -> Customer:
        customer = self.session.scalar(
            select(Customer)
            .options(
                selectinload(Customer.jobs).selectinload(Job.service),
                selectinload(Customer.jobs).selectinload(Job.originating_lead),
            )
            .where(Customer.id == customer_id, Customer.business_id == business_id)
        )
        if customer is None:
            raise LookupError("Customer was not found")
        return customer


class JobRepository(BusinessRepository[Job]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Job)

    def detailed(self, business_id: int) -> list[Job]:
        return list(
            self.session.scalars(
                select(Job)
                .options(
                    selectinload(Job.customer),
                    selectinload(Job.service),
                    selectinload(Job.originating_lead),
                    selectinload(Job.assignments).selectinload(JobAssignment.worker),
                )
                .where(Job.business_id == business_id)
                .order_by(Job.scheduled_start.desc(), Job.created_at.desc())
            )
            .unique()
            .all()
        )


class ServiceRepository(BusinessRepository[Service]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Service)


class WorkerRepository(BusinessRepository[Worker]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Worker)
