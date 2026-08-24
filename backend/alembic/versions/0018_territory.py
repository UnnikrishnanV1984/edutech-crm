"""users.territory / contacts.territory — minimal-viable territory-based
auto-assignment (GAP_FIXES_PLAN.md item 3). No connector emits a
territory signal on a raw lead today (no location field anywhere in the
lead schema), so this is admin-set on both sides: an admin tags a
counselor's territory and a contact's territory by hand, and the new
assign_by_territory workflow-rule action (app/workers/rules.py) matches
them, falling back to round-robin when either side has none set.

Nullable, no index — low-cardinality, optionally-filtered column with no
current query pattern that needs one (DATABASE_SCHEMA.md §5); add one
later if that changes.

Revision ID: 0018
Revises: 0017
Create Date: 2026-08-24
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN territory TEXT NULL")
    op.execute("ALTER TABLE contacts ADD COLUMN territory TEXT NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE contacts DROP COLUMN IF EXISTS territory")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS territory")
