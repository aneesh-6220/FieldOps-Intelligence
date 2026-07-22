"""Engine and transaction-scoped session management."""

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from enum import StrEnum

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.database.base import Base


def _enable_sqlite_foreign_keys(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection: object, _connection_record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def build_engine(database_url: str | None = None) -> Engine:
    """Construct an engine with SQLite safety settings when applicable."""
    url = database_url or get_settings().database_url
    kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}
    engine = create_engine(url, pool_pre_ping=True, **kwargs)
    if url.startswith("sqlite"):
        _enable_sqlite_foreign_keys(engine)
    return engine


class WorkspaceMode(StrEnum):
    """The physically separate store used for the current UI session."""

    OPERATIONAL = "operational"
    DEMO = "demo"


settings = get_settings()
engine = build_engine(settings.database_url)
demo_engine = build_engine(settings.demo_database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
DemoSessionLocal = sessionmaker(bind=demo_engine, autoflush=False, expire_on_commit=False)
_active_workspace: ContextVar[WorkspaceMode] = ContextVar(
    "fieldops_active_workspace", default=WorkspaceMode.OPERATIONAL
)


def set_active_workspace(workspace: WorkspaceMode) -> None:
    """Route implicit page sessions to the selected physical database."""
    _active_workspace.set(workspace)


def get_active_workspace() -> WorkspaceMode:
    """Return the database selected for the current execution context."""
    return _active_workspace.get()


def session_factory_for(workspace: WorkspaceMode) -> sessionmaker[Session]:
    """Return the session factory for an explicit workspace."""
    return DemoSessionLocal if workspace == WorkspaceMode.DEMO else SessionLocal


def engine_for(workspace: WorkspaceMode) -> Engine:
    """Return the engine for an explicit workspace."""
    return demo_engine if workspace == WorkspaceMode.DEMO else engine


@contextmanager
def session_scope(
    factory: sessionmaker[Session] | None = None,
    *,
    workspace: WorkspaceMode | None = None,
) -> Generator[Session, None, None]:
    """Commit a unit of work or roll it back atomically."""
    selected_factory = factory or session_factory_for(workspace or get_active_workspace())
    session = selected_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_schema(
    target_engine: Engine | None = None, *, workspace: WorkspaceMode | None = None
) -> None:
    """Create all tables for tests and first-run local convenience."""
    selected_engine = target_engine or engine_for(workspace or get_active_workspace())
    Base.metadata.create_all(selected_engine)
