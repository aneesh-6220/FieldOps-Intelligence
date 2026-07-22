"""Worker directory management."""

from sqlalchemy.orm import Session

from app.database.models import Worker
from app.database.repositories import WorkerRepository
from app.schemas.worker import WorkerCreate
from app.services.activity_service import record_activity


class WorkerService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = WorkerRepository(session)

    def create(self, data: WorkerCreate) -> Worker:
        worker = self.repository.add(Worker(**data.model_dump()))
        record_activity(
            self.session,
            worker.business_id,
            "worker",
            worker.id,
            "created",
            f"Worker {worker.display_name} created",
        )
        return worker

    def update(self, worker_id: int, business_id: int, data: WorkerCreate) -> Worker:
        worker = self.repository.require_for_business(worker_id, business_id)
        self.repository.update(worker, data.model_dump(exclude={"business_id"}))
        record_activity(
            self.session,
            business_id,
            "worker",
            worker.id,
            "updated",
            f"Worker {worker.display_name} updated",
        )
        return worker
