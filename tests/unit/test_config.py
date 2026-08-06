"""Workspace database URL validation and secret-safety tests."""

from pathlib import Path

import pytest

from app.config import ConfigurationError, Settings

PASSWORD = "sUperSecret123"
OPERATIONAL_PG = (
    f"postgresql+psycopg://summit:{PASSWORD}@db.example.net/fieldops_operational?sslmode=require"
)
DEMO_PG = f"postgresql+psycopg://summit:{PASSWORD}@db.example.net/fieldops_demo?sslmode=require"


def _settings(operational: str, demo: str) -> Settings:
    return Settings(database_url=operational, demo_database_url=demo)


def test_different_sqlite_urls_are_accepted(tmp_path: Path) -> None:
    settings = _settings(
        f"sqlite:///{tmp_path / 'operational.db'}", f"sqlite:///{tmp_path / 'demo.db'}"
    )
    assert settings.database_dialect == "sqlite"
    assert settings.sqlite_path is not None
    assert settings.demo_sqlite_path is not None


def test_different_postgresql_urls_are_accepted() -> None:
    settings = _settings(OPERATIONAL_PG, DEMO_PG)
    assert settings.database_dialect == "postgresql+psycopg"
    assert settings.demo_database_dialect == "postgresql+psycopg"
    assert settings.sqlite_path is None
    assert settings.demo_sqlite_path is None


def test_identical_sqlite_urls_are_rejected(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'shared.db'}"
    with pytest.raises(ConfigurationError, match="different locations"):
        _settings(url, url)


def test_identical_postgresql_urls_are_rejected() -> None:
    with pytest.raises(ConfigurationError, match="different locations"):
        _settings(OPERATIONAL_PG, OPERATIONAL_PG)


def test_equivalent_sqlite_paths_are_rejected_when_written_differently(tmp_path: Path) -> None:
    direct = f"sqlite:///{tmp_path / 'shared.db'}"
    indirect = f"sqlite:///{tmp_path / 'nested' / '..' / 'shared.db'}"
    with pytest.raises(ConfigurationError, match="different locations"):
        _settings(direct, indirect)


def test_equivalent_postgresql_targets_are_rejected_when_written_differently() -> None:
    same_database_different_spelling = (
        f"postgresql+psycopg://other:{PASSWORD}@DB.EXAMPLE.NET/fieldops_operational"
    )
    with pytest.raises(ConfigurationError, match="different locations"):
        _settings(OPERATIONAL_PG, same_database_different_spelling)


def test_blank_database_urls_are_rejected() -> None:
    with pytest.raises(ConfigurationError, match="FIELDOPS_DATABASE_URL"):
        _settings("   ", DEMO_PG)
    with pytest.raises(ConfigurationError, match="FIELDOPS_DEMO_DATABASE_URL"):
        _settings(OPERATIONAL_PG, "   ")


def test_validation_failure_never_exposes_connection_details() -> None:
    with pytest.raises(ConfigurationError) as failure:
        _settings(OPERATIONAL_PG, OPERATIONAL_PG)
    rendered = f"{failure.value!s} {failure.value!r}"
    for secret in [PASSWORD, "summit", "db.example.net", "sslmode", "postgresql+psycopg"]:
        assert secret not in rendered


def test_settings_repr_never_exposes_connection_details() -> None:
    rendered = repr(_settings(OPERATIONAL_PG, DEMO_PG))
    for secret in [PASSWORD, "summit", "db.example.net", "sslmode"]:
        assert secret not in rendered


def test_dialect_properties_expose_only_the_driver_name() -> None:
    settings = _settings(OPERATIONAL_PG, DEMO_PG)
    for value in [settings.database_dialect, settings.demo_database_dialect]:
        assert value == "postgresql+psycopg"
        assert PASSWORD not in value
        assert "db.example.net" not in value
