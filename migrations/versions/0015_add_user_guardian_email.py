"""add guardian_email to users

Revision ID: 0015
Revises: 0014
Create Date: 2026-07-16 00:00:00.000000

Additive, nullable — set only for role == CHILD, pointing to the parent
account's real email so password-recovery links reach an inbox someone
actually reads (a child's `email` is a system-generated, non-deliverable
address). See issue_password_setup_link.
"""

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("guardian_email", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "guardian_email")
