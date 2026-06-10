"""add annual_reading_goal to users

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-10 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("annual_reading_goal", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "annual_reading_goal")
