"""Deployment-readiness checks for the operational and demo databases."""

from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.base import Base
from app.database.engine import build_engine
from app.database.models import Business, Customer, Job, Lead, Service, Worker
from app.database.seed import seed_demo_data
from app.schemas.business import BusinessCreate
from app.services.workspace_service import WorkspaceService
from app.utils.database_url import database_dialect
from scripts.check_deployment import (
    DEMO,
    DEMO_WORKSPACE,
    EMPTY,
    OPERATIONAL,
    REAL_WORKSPACE,
    WorkspaceReport,
    check_database,
    ensure_schema,
    format_report,
    main,
    run_checks,
)

PASSWORD = "sUperSecret123"
LEAKY_PG = (
    f"postgresql+psycopg://summit:{PASSWORD}@db.example.net/fieldops_operational?sslmode=require"
)


def _sqlite_url(path: Path) -> str:
    return f"sqlite:///{path}"


def _create_real_workspace(url: str) -> None:
    engine = build_engine(url)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        WorkspaceService(session).create_operational_workspace(
            BusinessCreate(
                name="Summit Outdoor Services",
                industry="Landscaping and seasonal maintenance",
                currency_code="CAD",
                timezone="America/Toronto",
            )
        )
        session.commit()
    engine.dispose()


def _create_demo_workspace(url: str) -> None:
    engine = build_engine(url)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_demo_data(session)
        session.commit()
    engine.dispose()


def _create_marked_business(url: str, *, demo_data: bool) -> None:
    engine = build_engine(url)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            Business(
                name="Summit Outdoor Services",
                industry="Landscaping and seasonal maintenance",
                currency_code="CAD",
                timezone="America/Toronto",
                country="Canada",
                default_tax_rate=Decimal("0.13"),
                settings={"demo_data": demo_data},
            )
        )
        session.commit()
    engine.dispose()


def test_empty_operational_database_is_accepted(tmp_path: Path) -> None:
    report = check_database(OPERATIONAL, _sqlite_url(tmp_path / "operational.db"))
    assert report.ok
    assert report.connected
    assert report.schema_ready
    assert report.workspace_state == EMPTY


def test_empty_demo_database_is_accepted(tmp_path: Path) -> None:
    report = check_database(DEMO, _sqlite_url(tmp_path / "demo.db"))
    assert report.ok
    assert report.workspace_state == EMPTY


def test_schema_creation_inserts_no_records(tmp_path: Path) -> None:
    engine = build_engine(_sqlite_url(tmp_path / "operational.db"))
    assert ensure_schema(engine) is True
    with Session(engine) as session:
        for model in [Business, Lead, Customer, Worker, Service, Job]:
            assert session.scalar(select(func.count()).select_from(model)) == 0
    engine.dispose()


def test_readiness_check_never_seeds_either_database(tmp_path: Path) -> None:
    operational = _sqlite_url(tmp_path / "operational.db")
    demo = _sqlite_url(tmp_path / "demo.db")
    reports, problems = run_checks(operational, demo)
    assert problems == []
    for url in [operational, demo]:
        engine = build_engine(url)
        with Session(engine) as session:
            assert session.scalar(select(func.count()).select_from(Business)) == 0
            assert session.scalar(select(func.count()).select_from(Lead)) == 0
        engine.dispose()
    assert {report.workspace_state for report in reports} == {EMPTY}


def test_initialized_real_operational_workspace_is_accepted(tmp_path: Path) -> None:
    url = _sqlite_url(tmp_path / "operational.db")
    _create_real_workspace(url)
    report = check_database(OPERATIONAL, url)
    assert report.ok
    assert report.workspace_state == REAL_WORKSPACE


def test_initialized_demo_workspace_is_accepted(tmp_path: Path) -> None:
    url = _sqlite_url(tmp_path / "demo.db")
    _create_demo_workspace(url)
    report = check_database(DEMO, url)
    assert report.ok
    assert report.workspace_state == DEMO_WORKSPACE


def test_operational_database_rejects_demo_data(tmp_path: Path) -> None:
    url = _sqlite_url(tmp_path / "operational.db")
    _create_marked_business(url, demo_data=True)
    report = check_database(OPERATIONAL, url)
    assert not report.ok
    assert report.problem is not None
    assert "demo data" in report.problem


def test_demo_database_rejects_real_workspace(tmp_path: Path) -> None:
    url = _sqlite_url(tmp_path / "demo.db")
    _create_marked_business(url, demo_data=False)
    report = check_database(DEMO, url)
    assert not report.ok
    assert report.problem is not None
    assert "real workspace" in report.problem


def test_identical_urls_are_rejected_before_connecting(tmp_path: Path) -> None:
    url = _sqlite_url(tmp_path / "shared.db")
    reports, problems = run_checks(url, url)
    assert reports == []
    assert problems and "same database" in problems[0]


def test_connection_failure_is_nonzero_and_sanitized(tmp_path: Path) -> None:
    unreachable = _sqlite_url(tmp_path / "missing-directory" / "operational.db")
    report = check_database(OPERATIONAL, unreachable)
    assert not report.ok
    assert report.connected is False
    assert report.schema_ready is False
    assert report.problem is not None
    assert "OperationalError" in report.problem
    assert str(tmp_path) not in report.problem
    assert "missing-directory" not in report.problem

    reports, problems = run_checks(unreachable, _sqlite_url(tmp_path / "demo.db"))
    output = format_report(reports, problems)
    assert problems
    assert str(tmp_path) not in output
    assert "sqlite:///" not in output


def test_report_output_contains_no_connection_details(tmp_path: Path) -> None:
    operational = _sqlite_url(tmp_path / "operational.db")
    _create_real_workspace(operational)
    demo = _sqlite_url(tmp_path / "demo.db")
    _create_demo_workspace(demo)

    reports, problems = run_checks(operational, demo)
    output = format_report(reports, problems)

    assert problems == []
    assert "Ready to deploy." in output
    assert f"  {OPERATIONAL}" in output and f"  {DEMO}" in output
    for forbidden in [str(tmp_path), "sqlite:///", "operational.db", "demo.db", "?", "@"]:
        assert forbidden not in output


def test_report_of_postgresql_urls_shows_only_the_dialect() -> None:
    # Built directly so the test never opens a network connection.
    report = WorkspaceReport(
        role=OPERATIONAL,
        dialect=database_dialect(LEAKY_PG),
        connected=True,
        schema_ready=True,
        workspace_state=EMPTY,
    )
    output = format_report([report], [])
    assert "postgresql+psycopg" in output
    for secret in [PASSWORD, "summit", "db.example.net", "sslmode", LEAKY_PG]:
        assert secret not in output


def test_main_exits_zero_when_both_databases_are_ready(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import app.config

    operational = _sqlite_url(tmp_path / "operational.db")
    demo = _sqlite_url(tmp_path / "demo.db")
    monkeypatch.setattr(
        app.config,
        "get_settings",
        lambda: app.config.Settings(database_url=operational, demo_database_url=demo),
    )
    assert main() == 0
    assert "Ready to deploy." in capsys.readouterr().out


def test_main_exits_nonzero_when_operational_holds_demo_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import app.config

    operational = _sqlite_url(tmp_path / "operational.db")
    _create_marked_business(operational, demo_data=True)
    demo = _sqlite_url(tmp_path / "demo.db")
    monkeypatch.setattr(
        app.config,
        "get_settings",
        lambda: app.config.Settings(database_url=operational, demo_database_url=demo),
    )
    assert main() == 1
    output = capsys.readouterr().out
    assert "Not ready:" in output
    assert str(tmp_path) not in output


def test_main_reports_misconfiguration_without_exposing_urls(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import app.config

    def explode() -> app.config.Settings:
        return app.config.Settings(database_url=LEAKY_PG, demo_database_url=LEAKY_PG)

    monkeypatch.setattr(app.config, "get_settings", explode)
    assert main() == 1
    output = capsys.readouterr().out
    assert "Not ready:" in output
    for secret in [PASSWORD, "summit", "db.example.net", "sslmode"]:
        assert secret not in output
