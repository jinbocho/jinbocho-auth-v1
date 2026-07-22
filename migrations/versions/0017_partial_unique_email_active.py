"""make users.email unique only among active users

Revision ID: 0017
Revises: 0016
Create Date: 2026-07-22 00:00:00.000000

Disabled users kept their email under the plain UNIQUE constraint forever,
so a family could never reuse that address for a new or renamed member —
the email/create-user dedup checks in the application layer were fixed to
skip inactive matches, but the DB-level constraint still rejected the
INSERT/UPDATE regardless. Replaced with a partial unique index scoped to
is_active = true; disabled accounts may now share an email with an active
one or with each other.
"""

import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("users_email_key", "users", type_="unique")
    op.create_index(
        "uq_users_email_active",
        "users",
        ["email"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )


def downgrade() -> None:
    op.drop_index("uq_users_email_active", table_name="users")
    op.create_unique_constraint("users_email_key", "users", ["email"])
