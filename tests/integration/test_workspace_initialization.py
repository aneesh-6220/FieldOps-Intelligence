"""Real/demo initialization and physical database isolation tests."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.database.base import Base
from app.database.models import ActivityLog, Business, Customer, Job, Lead, Service, Worker
from app.database.session import WorkspaceMode, build_engine
from app.schemas.business import BusinessCreate
from app.services.workspace_service import WorkspaceService, should_show_demo_banner


@pytest.fixture
def workspace_factories(
    tmp_path: Path,
) -> Iterator[tuple[sessionmaker[Session], sessionmaker[Session], Engine, Engine]]:
    operational_engine = build_engine(f"sqlite:///{tmp_path / 'operational.db'}")
    demo_engine = build_engine(f"sqlite:///{tmp_path / 'demo.db'}")
    Base.metadata.create_all(operational_engine)
    Base.metadata.create_all(demo_engine)
    operational_factory = sessionmaker(
        bind=operational_engine, expire_on_commit=False, autoflush=False
    )
    demo_factory = sessionmaker(bind=demo_engine, expire_on_commit=False, autoflush=False)
    yield operational_factory, demo_factory, operational_engine, demo_engine
    operational_engine.dispose()
    demo_engine.dispose()


def _real_workspace() -> BusinessCreate:
    return BusinessCreate(
        name="Summit Outdoor Services",
        industry="Landscaping and seasonal maintenance",
        currency_code="CAD",
        timezone="America/Toronto",
    )


def _count(session: Session, model: type[object]) -> int:
    return int(session.scalar(select(func.count()).select_from(model)) or 0)


def test_blank_first_run_has_no_workspace_in_either_database(
    workspace_factories: tuple[sessionmaker[Session], sessionmaker[Session], Engine, Engine],
) -> None:
    operational_factory, demo_factory, _, _ = workspace_factories
    with operational_factory() as operational, demo_factory() as demo:
        assert WorkspaceService(operational).get_business() is None
        assert WorkspaceService(demo).get_business() is None


def test_real_workspace_creation_is_blank_and_not_demo(
    workspace_factories: tuple[sessionmaker[Session], sessionmaker[Session], Engine, Engine],
) -> None:
    operational_factory, _, _, _ = workspace_factories
    with operational_factory.begin() as session:
        business = WorkspaceService(session).create_operational_workspace(_real_workspace())
        assert business.settings["demo_data"] is False
        for model in [Lead, Customer, Worker, Job, Service, ActivityLog]:
            assert _count(session, model) == 0


def test_demo_workspace_creation_preserves_deterministic_seed(
    workspace_factories: tuple[sessionmaker[Session], sessionmaker[Session], Engine, Engine],
) -> None:
    _, demo_factory, _, _ = workspace_factories
    with demo_factory.begin() as session:
        business = WorkspaceService(session).initialize_demo_workspace()
        assert business.settings["demo_data"] is True
        assert _count(session, Lead) == 55
        assert _count(session, Customer) == 25
        assert _count(session, Worker) == 4
        assert _count(session, Job) == 40
        assert _count(session, Service) == 8


def test_operational_and_demo_records_are_physically_separate(
    workspace_factories: tuple[sessionmaker[Session], sessionmaker[Session], Engine, Engine],
) -> None:
    operational_factory, demo_factory, operational_engine, demo_engine = workspace_factories
    assert operational_engine.url.database != demo_engine.url.database
    with operational_factory.begin() as operational:
        WorkspaceService(operational).create_operational_workspace(_real_workspace())
    with demo_factory.begin() as demo:
        WorkspaceService(demo).initialize_demo_workspace()
    with operational_factory() as operational, demo_factory() as demo:
        assert _count(operational, Business) == 1
        assert _count(operational, Lead) == 0
        assert _count(demo, Business) == 1
        assert _count(demo, Lead) == 55


def test_demo_banner_requires_demo_store_and_demo_marker(
    workspace_factories: tuple[sessionmaker[Session], sessionmaker[Session], Engine, Engine],
) -> None:
    operational_factory, demo_factory, _, _ = workspace_factories
    with operational_factory.begin() as operational:
        real = WorkspaceService(operational).create_operational_workspace(_real_workspace())
        assert should_show_demo_banner(WorkspaceMode.OPERATIONAL, real) is False
    with demo_factory.begin() as demo:
        synthetic = WorkspaceService(demo).initialize_demo_workspace()
        assert should_show_demo_banner(WorkspaceMode.DEMO, synthetic) is True
        assert should_show_demo_banner(WorkspaceMode.OPERATIONAL, synthetic) is False


def test_demo_reset_cannot_modify_or_clear_operational_database(
    workspace_factories: tuple[sessionmaker[Session], sessionmaker[Session], Engine, Engine],
) -> None:
    operational_factory, demo_factory, _, _ = workspace_factories
    with operational_factory.begin() as operational:
        real = WorkspaceService(operational).create_operational_workspace(_real_workspace())
        real_name = real.name
    with demo_factory.begin() as demo:
        WorkspaceService(demo).initialize_demo_workspace()
    with demo_factory.begin() as demo:
        WorkspaceService(demo).reset_demo_workspace()
    with operational_factory() as operational:
        assert operational.scalar(select(Business.name)) == real_name
        assert _count(operational, Lead) == 0
    with (
        operational_factory.begin() as operational,
        pytest.raises(ValueError, match="operational workspace"),
    ):
        WorkspaceService(operational).reset_demo_workspace()
    with operational_factory() as operational:
        assert operational.scalar(select(Business.name)) == real_name
        assert _count(operational, Business) == 1
