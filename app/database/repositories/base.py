"""Small, typed repository abstractions over SQLAlchemy sessions."""

from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.database.base import Base


class Repository[ModelT: Base]:
    """Persistence operations shared by domain repositories."""

    def __init__(self, session: Session, model: type[ModelT]) -> None:
        self.session = session
        self.model = model

    def get(self, entity_id: int) -> ModelT | None:
        return self.session.get(self.model, entity_id)

    def require(self, entity_id: int) -> ModelT:
        entity = self.get(entity_id)
        if entity is None:
            raise LookupError(f"{self.model.__name__} {entity_id} was not found")
        return entity

    def add(self, entity: ModelT) -> ModelT:
        self.session.add(entity)
        self.session.flush()
        return entity

    def list_for_business(self, business_id: int) -> list[ModelT]:
        model: Any = self.model
        statement: Select[tuple[ModelT]] = select(self.model).where(
            model.business_id == business_id
        )
        return list(self.session.scalars(statement).all())

    def update(self, entity: ModelT, values: dict[str, Any]) -> ModelT:
        for key, value in values.items():
            setattr(entity, key, value)
        self.session.flush()
        return entity


class BusinessRepository[ModelT: Base](Repository[ModelT]):
    """Repository base enforcing tenant ownership."""

    def require_for_business(self, entity_id: int, business_id: int) -> ModelT:
        model: Any = self.model
        entity = self.session.scalar(
            select(self.model).where(
                model.id == entity_id,
                model.business_id == business_id,
            )
        )
        if entity is None:
            raise LookupError(f"{self.model.__name__} {entity_id} was not found")
        return entity
