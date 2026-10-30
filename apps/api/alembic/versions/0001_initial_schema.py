"""Create the initial WEAVE relational schema.

Revision ID: 0001_initial_schema
Revises:
"""

from __future__ import annotations

from alembic import op
from app import models  # noqa: F401
from app.db.base import Base

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the initial schema from the versioned SQLAlchemy model metadata."""
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    """Drop the initial schema in dependency order."""
    Base.metadata.drop_all(bind=op.get_bind())
