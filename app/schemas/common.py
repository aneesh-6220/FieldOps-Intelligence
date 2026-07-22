"""Shared schema configuration."""

from pydantic import BaseModel, ConfigDict


class Schema(BaseModel):
    """Base schema supporting ORM attribute validation."""

    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)
