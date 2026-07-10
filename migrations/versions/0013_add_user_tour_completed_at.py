"""add tour_completed_at to users

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-10 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("tour_completed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "tour_completed_at")
