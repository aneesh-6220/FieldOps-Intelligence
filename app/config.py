"""Typed runtime configuration loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.utils.database_url import database_dialect, normalized_target, sqlite_path


class ConfigurationError(Exception):
    """Raised for unsafe configuration.

    This is intentionally not a ``ValueError``. Pydantic wraps ``ValueError``
    into a ``ValidationError`` whose text echoes the offending input, which for
    a database URL would expose the password. Raising a plain exception keeps
    the message limited to the sanitized text below.
    """


class Settings(BaseSettings):
    """Application configuration with safe local defaults."""

    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="FIELDOPS_", extra="ignore", case_sensitive=False
    )

    app_name: str = "FieldOps Intelligence"
    database_url: str = Field(default="sqlite:///fieldops_operational.db", repr=False)
    demo_database_url: str = Field(default="sqlite:///fieldops_demo.db", repr=False)
    log_level: str = "INFO"
    auto_seed: bool = False
    stale_lead_days: int = Field(default=14, ge=1, le=365)
    cost_overrun_threshold: float = Field(default=0.20, ge=0, le=5)
    duration_overrun_threshold: float = Field(default=0.25, ge=0, le=5)
    concentration_threshold: float = Field(default=0.60, ge=0, le=1)
    low_sample_threshold: int = Field(default=5, ge=2, le=100)
    default_date_format: str = "%b %d, %Y"

    @model_validator(mode="after")
    def require_separate_workspace_databases(self) -> "Settings":
        if not self.database_url.strip():
            raise ConfigurationError("FIELDOPS_DATABASE_URL is not configured")
        if not self.demo_database_url.strip():
            raise ConfigurationError("FIELDOPS_DEMO_DATABASE_URL is not configured")
        if self._normalized_database_target(self.database_url) == self._normalized_database_target(
            self.demo_database_url
        ):
            raise ConfigurationError("Operational and demo databases must use different locations")
        return self

    @staticmethod
    def _normalized_database_target(url: str) -> str:
        return normalized_target(url)

    @property
    def sqlite_path(self) -> Path | None:
        """Return the local database path when SQLite is configured."""
        return sqlite_path(self.database_url)

    @property
    def demo_sqlite_path(self) -> Path | None:
        """Return the dedicated demo database path when SQLite is configured."""
        return sqlite_path(self.demo_database_url)

    @property
    def database_dialect(self) -> str:
        """Return the operational driver name only, safe to display."""
        return database_dialect(self.database_url)

    @property
    def demo_database_dialect(self) -> str:
        """Return the demo driver name only, safe to display."""
        return database_dialect(self.demo_database_url)


@lru_cache
def get_settings() -> Settings:
    """Return a process-cached settings object."""
    return Settings()
