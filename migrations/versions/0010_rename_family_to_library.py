"""rename family -> library (ADR-011 step 2)

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-06 00:00:00.000000

Renames the tenant concept from "family" to "library" on the live schema —
this service is already deployed, so unlike a pre-launch rewrite, the
previous migrations (0001-0009) must stay exactly as they ran in production.

RENAME TO / RENAME COLUMN are metadata-only operations in Postgres (no table
rewrite, no data movement), so this is safe to run against a populated
production database without a maintenance window. Index/constraint names are
renamed too, for readability, via ALTER INDEX / ALTER TABLE ... RENAME
CONSTRAINT — these are equally metadata-only.
"""

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.rename_table("families", "libraries")
    op.alter_column("users", "family_id", new_column_name="library_id")
    op.execute("ALTER INDEX idx_users_family_id RENAME TO idx_users_library_id")


def downgrade() -> None:
    op.execute("ALTER INDEX idx_users_library_id RENAME TO idx_users_family_id")
    op.alter_column("users", "library_id", new_column_name="family_id")
    op.rename_table("libraries", "families")
