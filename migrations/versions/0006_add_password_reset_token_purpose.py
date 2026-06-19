"""add purpose to password_reset_tokens

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-19 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "password_reset_tokens",
        sa.Column("purpose", sa.String(20), nullable=False, server_default="reset"),
    )


def downgrade() -> None:
    op.drop_column("password_reset_tokens", "purpose")
