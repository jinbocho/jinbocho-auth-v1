"""add theme preferences to users

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-12 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("theme_name", sa.String(20), nullable=True))
    op.add_column("users", sa.Column("theme_mode", sa.String(10), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "theme_mode")
    op.drop_column("users", "theme_name")
