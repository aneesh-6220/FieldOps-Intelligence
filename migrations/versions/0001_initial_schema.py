"""Initial relational schema.

Revision ID: 0001
Revises: None
"""

from alembic import op

from app.database.base import Base
from app.database import models  # noqa: F401

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the initial schema from version-controlled metadata."""
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    """Drop all initial tables."""
    Base.metadata.drop_all(bind=op.get_bind())

