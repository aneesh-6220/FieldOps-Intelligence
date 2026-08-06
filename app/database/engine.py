"""Engine construction for SQLite and managed PostgreSQL.

This module deliberately holds no module-level engines. Deployment tooling can
import ``build_engine`` and open its own connections without instantiating the
application's global operational and demo engines.
"""

from typing import Any

from sqlalchemy import Engine, create_engine, event

from app.utils.database_url import is_sqlite_url


def _enable_sqlite_foreign_keys(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection: object, _connection_record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def build_engine(database_url: str) -> Engine:
    """Construct an engine, applying SQLite safety settings when applicable.

    PostgreSQL URLs are passed through untouched so provider-supplied query
    parameters such as ``sslmode=require`` keep working.
    """
    sqlite = is_sqlite_url(database_url)
    kwargs: dict[str, Any] = {"connect_args": {"check_same_thread": False}} if sqlite else {}
    engine = create_engine(database_url, pool_pre_ping=True, **kwargs)
    if sqlite:
        _enable_sqlite_foreign_keys(engine)
    return engine
