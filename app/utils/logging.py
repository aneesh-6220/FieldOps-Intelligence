"""Central logging configuration."""

import logging

from app.config import get_settings


def configure_logging() -> None:
    """Configure consistent application logging without customer record payloads."""
    logging.basicConfig(
        level=getattr(logging, get_settings().log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
