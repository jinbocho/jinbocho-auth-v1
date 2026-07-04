"""add consent_privacy_version, consent_terms_version, consent_at to users

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-03 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("consent_privacy_version", sa.String(length=20), nullable=True))
    op.add_column("users", sa.Column("consent_terms_version", sa.String(length=20), nullable=True))
    op.add_column("users", sa.Column("consent_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "consent_at")
    op.drop_column("users", "consent_terms_version")
    op.drop_column("users", "consent_privacy_version")
