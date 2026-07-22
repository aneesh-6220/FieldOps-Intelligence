"""Typed runtime configuration loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration with safe local defaults."""

    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="FIELDOPS_", extra="ignore", case_sensitive=False
    )

    app_name: str = "FieldOps Intelligence"
    database_url: str = "sqlite:///fieldops.db"
    log_level: str = "INFO"
    auto_seed: bool = False
    stale_lead_days: int = Field(default=14, ge=1, le=365)
    cost_overrun_threshold: float = Field(default=0.20, ge=0, le=5)
    duration_overrun_threshold: float = Field(default=0.25, ge=0, le=5)
    concentration_threshold: float = Field(default=0.60, ge=0, le=1)
    low_sample_threshold: int = Field(default=5, ge=2, le=100)
    default_date_format: str = "%b %d, %Y"

    @property
    def sqlite_path(self) -> Path | None:
        """Return the local database path when SQLite is configured."""
        prefix = "sqlite:///"
        return (
            Path(self.database_url.removeprefix(prefix))
            if self.database_url.startswith(prefix)
            else None
        )


@lru_cache
def get_settings() -> Settings:
    """Return a process-cached settings object."""
    return Settings()
