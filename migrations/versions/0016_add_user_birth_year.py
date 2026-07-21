"""add birth_year to users

Revision ID: 0016
Revises: 0015
Create Date: 2026-07-17 00:00:00.000000

Additive, nullable — year only, not full date of birth (GDPR data
minimization). Drives the kids-mode age band on the frontend and the AI
quiz-difficulty prompt. See jinbocho-docs/backlog/BACKLOG_KIDS_READING_EDUCATION.md
KID-01.
"""

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("birth_year", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "birth_year")
