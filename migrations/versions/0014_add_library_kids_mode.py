"""add kids_mode_enabled to libraries

Revision ID: 0014
Revises: 0013
Create Date: 2026-07-16 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "libraries",
        sa.Column("kids_mode_enabled", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("libraries", "kids_mode_enabled")
