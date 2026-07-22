"""Configurable service catalog management."""

from sqlalchemy.orm import Session

from app.database.models import Service
from app.database.repositories import ServiceRepository
from app.schemas.service import ServiceCreate
from app.services.activity_service import record_activity


class ServiceCatalogService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = ServiceRepository(session)

    def create(self, data: ServiceCreate) -> Service:
        service = self.repository.add(Service(**data.model_dump()))
        record_activity(
            self.session,
            service.business_id,
            "service",
            service.id,
            "created",
            f"Service {service.name} created",
        )
        return service

    def archive(self, service_id: int, business_id: int) -> Service:
        service = self.repository.require_for_business(service_id, business_id)
        service.is_active = False
        return service

    def update(self, service_id: int, business_id: int, data: ServiceCreate) -> Service:
        service = self.repository.require_for_business(service_id, business_id)
        self.repository.update(service, data.model_dump(exclude={"business_id"}))
        record_activity(
            self.session,
            business_id,
            "service",
            service.id,
            "updated",
            f"Service {service.name} updated",
        )
        return service
