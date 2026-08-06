"""Safe comparison and display helpers for database URLs.

Nothing here connects to a database or builds an engine, so configuration and
presentation code can reason about URLs without importing engine state. Every
public helper returns values that are safe to print: usernames, passwords,
hosts, and query parameters are never included.
"""

from pathlib import Path

from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

SQLITE_PREFIX = "sqlite:///"


def normalized_target(url: str) -> str:
    """Return an opaque key identifying the physical database a URL points at.

    SQLite files are resolved so two spellings of one path compare equal.
    Server URLs collapse to backend, host, port, and database name so the same
    database compares equal regardless of credentials or query parameters such
    as ``sslmode``.
    """
    if url.startswith(SQLITE_PREFIX):
        return str(Path(url.removeprefix(SQLITE_PREFIX)).resolve())
    try:
        parsed = make_url(url)
    except ArgumentError:
        return url
    if parsed.get_backend_name() == "sqlite":
        return str(Path(parsed.database).resolve()) if parsed.database else url
    return "|".join(
        [
            parsed.get_backend_name(),
            (parsed.host or "").lower(),
            str(parsed.port or ""),
            parsed.database or "",
        ]
    )


def is_sqlite_url(url: str) -> bool:
    """Return whether the URL addresses SQLite."""
    if url.startswith("sqlite"):
        return True
    try:
        return make_url(url).get_backend_name() == "sqlite"
    except ArgumentError:
        return False


def sqlite_path(url: str) -> Path | None:
    """Return the local file path when a SQLite URL is configured."""
    return Path(url.removeprefix(SQLITE_PREFIX)) if url.startswith(SQLITE_PREFIX) else None


def database_dialect(url: str) -> str:
    """Return only the driver name, never credentials, host, or query parameters."""
    try:
        return make_url(url).drivername
    except ArgumentError:
        return "unknown"
