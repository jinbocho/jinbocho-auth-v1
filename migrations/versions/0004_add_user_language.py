"""add language preference to users

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-10 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("language", sa.String(2), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "language")
