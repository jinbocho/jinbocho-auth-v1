"""add user_library_memberships table, users.last_selected_library_id, backfill

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-06 00:00:00.000001

Additive migration (ADR-011 step 2, part 2 — runs after 0010's family->library
rename): introduces the membership model alongside the existing
users.library_id/role scalar columns, which are intentionally left in place
for now (dropping them is a later cleanup once every service reads
exclusively from user_library_memberships). Every existing user gets exactly
one backfilled membership row so current single-library behavior is
unchanged until the application layer starts using memberships.
"""

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_library_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "library_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("libraries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column(
            "invited_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("invited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "library_id", name="uq_membership_user_library"),
    )
    op.create_index("idx_memberships_user_status", "user_library_memberships", ["user_id", "status"])
    op.create_index("idx_memberships_library_status", "user_library_memberships", ["library_id", "status"])
    op.create_index("idx_memberships_library_role", "user_library_memberships", ["library_id", "role"])

    op.add_column(
        "users",
        sa.Column(
            "last_selected_library_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("libraries.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # Backfill: one active membership per existing user, mirroring their
    # current (library_id, role) scalar. Row-by-row in Python rather than a
    # single INSERT ... SELECT because we need a fresh UUID per row without
    # relying on a Postgres extension (pgcrypto) that may not be installed.
    bind = op.get_bind()
    users_table = sa.table(
        "users",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("library_id", postgresql.UUID(as_uuid=True)),
        sa.column("role", sa.String),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("last_selected_library_id", postgresql.UUID(as_uuid=True)),
    )
    memberships_table = sa.table(
        "user_library_memberships",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("user_id", postgresql.UUID(as_uuid=True)),
        sa.column("library_id", postgresql.UUID(as_uuid=True)),
        sa.column("role", sa.String),
        sa.column("status", sa.String),
        sa.column("joined_at", sa.DateTime(timezone=True)),
    )

    rows = bind.execute(sa.select(users_table.c.id, users_table.c.library_id, users_table.c.role, users_table.c.created_at)).fetchall()
    for row in rows:
        bind.execute(
            memberships_table.insert().values(
                id=uuid.uuid4(),
                user_id=row.id,
                library_id=row.library_id,
                role=row.role,
                status="active",
                joined_at=row.created_at,
            )
        )
    if rows:
        bind.execute(
            users_table.update().values(last_selected_library_id=users_table.c.library_id)
        )


def downgrade() -> None:
    op.drop_column("users", "last_selected_library_id")
    op.drop_index("idx_memberships_library_role", table_name="user_library_memberships")
    op.drop_index("idx_memberships_library_status", table_name="user_library_memberships")
    op.drop_index("idx_memberships_user_status", table_name="user_library_memberships")
    op.drop_table("user_library_memberships")
