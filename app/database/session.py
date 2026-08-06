"""Engine and transaction-scoped session management."""

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from enum import StrEnum

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.database.base import Base
from app.database.engine import build_engine as _build_engine

__all__ = [
    "DemoSessionLocal",
    "SessionLocal",
    "WorkspaceMode",
    "build_engine",
    "create_schema",
    "demo_engine",
    "engine",
    "engine_for",
    "get_active_workspace",
    "session_factory_for",
    "session_scope",
    "set_active_workspace",
]


def build_engine(database_url: str | None = None) -> Engine:
    """Construct an engine for an explicit URL, or the configured operational one."""
    return _build_engine(database_url or get_settings().database_url)


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
