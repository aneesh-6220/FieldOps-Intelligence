"""Verify that the configured operational and demo databases are safe to deploy against.

The check connects to both databases, creates the baseline schema if it is
missing, and inspects the workspace each database holds. It never seeds, never
writes business records, and never prints a URL, username, password, hostname,
or query parameter.

Usage:

    python scripts/check_deployment.py
"""

import sys
from dataclasses import dataclass
from pathlib import Path

if __package__ in (None, ""):  # Allow `python scripts/check_deployment.py` from the repo root.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import Engine, inspect, select  # noqa: E402
from sqlalchemy.exc import SQLAlchemyError  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.database.base import Base  # noqa: E402
from app.database.engine import build_engine  # noqa: E402
from app.database.models import Business  # noqa: E402
from app.utils.database_url import database_dialect, normalized_target  # noqa: E402

OPERATIONAL = "operational"
DEMO = "demo"

EMPTY = "empty"
REAL_WORKSPACE = "real workspace"
DEMO_WORKSPACE = "demo workspace"
UNKNOWN = "unknown"


@dataclass(frozen=True)
class WorkspaceReport:
    """A sanitized, printable summary of one database."""

    role: str
    dialect: str
    connected: bool
    schema_ready: bool
    workspace_state: str
    problem: str | None = None

    @property
    def ok(self) -> bool:
        return self.problem is None


def _sanitized_failure(exc: SQLAlchemyError) -> str:
    """Describe a driver failure without echoing the URL it came from.

    SQLAlchemy and psycopg both embed the host, port, and sometimes the user in
    their exception text, so only the exception class name is reported.
    """
    return (
        f"{type(exc).__name__} while connecting. "
        "Check the configured URL in your environment or Streamlit secrets."
    )


def ensure_schema(engine: Engine) -> bool:
    """Create the baseline tables if absent and report whether they are all present.

    This creates structure only. No row is ever inserted.
    """
    Base.metadata.create_all(engine)
    present = set(inspect(engine).get_table_names())
    return set(Base.metadata.tables).issubset(present)


def classify_workspace(session: Session) -> str:
    """Return the workspace a database holds, based only on the demo marker."""
    businesses = list(session.scalars(select(Business).order_by(Business.id)).all())
    if not businesses:
        return EMPTY
    markers = {business.settings.get("demo_data") is True for business in businesses}
    if markers == {True}:
        return DEMO_WORKSPACE
    if markers == {False}:
        return REAL_WORKSPACE
    return UNKNOWN


def _expected_state_problem(role: str, state: str) -> str | None:
    if state == UNKNOWN:
        return f"The {role} database mixes demo and real businesses."
    if role == OPERATIONAL and state == DEMO_WORKSPACE:
        return "The operational database contains demo data. Point it at a clean database."
    if role == DEMO and state == REAL_WORKSPACE:
        return "The demo database contains a real workspace. Point it at the demo database."
    return None


def check_database(role: str, url: str) -> WorkspaceReport:
    """Connect, ensure the schema, and confirm the database holds the expected workspace."""
    dialect = database_dialect(url)
    engine = build_engine(url)
    try:
        with engine.connect():
            pass
        schema_ready = ensure_schema(engine)
        with Session(engine) as session:
            state = classify_workspace(session)
    except SQLAlchemyError as exc:
        return WorkspaceReport(
            role=role,
            dialect=dialect,
            connected=False,
            schema_ready=False,
            workspace_state=UNKNOWN,
            problem=_sanitized_failure(exc),
        )
    finally:
        engine.dispose()

    problem = _expected_state_problem(role, state)
    if problem is None and not schema_ready:
        problem = f"The {role} database is missing expected tables."
    return WorkspaceReport(
        role=role,
        dialect=dialect,
        connected=True,
        schema_ready=schema_ready,
        workspace_state=state,
        problem=problem,
    )


def check_urls(operational_url: str, demo_url: str) -> list[str]:
    """Validate the URL pair itself, before any connection is attempted."""
    problems: list[str] = []
    if not operational_url.strip():
        problems.append("FIELDOPS_DATABASE_URL is not configured.")
    if not demo_url.strip():
        problems.append("FIELDOPS_DEMO_DATABASE_URL is not configured.")
    if not problems and normalized_target(operational_url) == normalized_target(demo_url):
        problems.append(
            "The operational and demo URLs resolve to the same database. "
            "Use two separate databases."
        )
    return problems


def run_checks(operational_url: str, demo_url: str) -> tuple[list[WorkspaceReport], list[str]]:
    """Run every readiness check and return sanitized reports plus blocking problems."""
    problems = check_urls(operational_url, demo_url)
    if problems:
        return [], problems
    reports = [
        check_database(OPERATIONAL, operational_url),
        check_database(DEMO, demo_url),
    ]
    return reports, [report.problem for report in reports if report.problem is not None]


def format_report(reports: list[WorkspaceReport], problems: list[str]) -> str:
    """Render a sanitized, human-readable result."""
    lines = ["FieldOps deployment readiness", ""]
    for report in reports:
        lines.extend(
            [
                f"  {report.role}",
                f"    dialect          {report.dialect}",
                f"    connection       {'ok' if report.connected else 'failed'}",
                f"    schema           {'ready' if report.schema_ready else 'not ready'}",
                f"    workspace        {report.workspace_state}",
                "",
            ]
        )
    if problems:
        lines.append("Not ready:")
        lines.extend(f"  - {problem}" for problem in problems)
    else:
        lines.append("Ready to deploy.")
    return "\n".join(lines)


def main() -> int:
    from app.config import ConfigurationError, get_settings

    try:
        settings = get_settings()
    except ConfigurationError as exc:
        print(f"FieldOps deployment readiness\n\nNot ready:\n  - {exc}.")
        return 1
    reports, problems = run_checks(settings.database_url, settings.demo_database_url)
    print(format_report(reports, problems))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
