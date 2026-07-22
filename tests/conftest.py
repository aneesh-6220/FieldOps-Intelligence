"""Shared isolated SQLite fixtures."""

from collections.abc import Generator
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.database.models import Business


@pytest.fixture
def session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def foreign_keys(connection: object, _record: object) -> None:
        cursor = connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db_session:
        yield db_session
        db_session.rollback()
    Base.metadata.drop_all(engine)


@pytest.fixture
def business(session: Session) -> Business:
    entity = Business(
        name="Test Field Services",
        industry="Property maintenance",
        currency_code="CAD",
        timezone="America/Toronto",
        country="Canada",
        default_tax_rate=Decimal("0.13"),
        settings={},
    )
    session.add(entity)
    session.flush()
    return entity
