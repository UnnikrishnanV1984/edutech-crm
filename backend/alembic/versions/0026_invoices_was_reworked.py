"""invoices.was_reworked — deviation from PIPELINE_AND_REVENUE_PLAN.md's
original task 5 DDL, found while implementing task 9's rework-rate KPI.
"% of invoices that ever passed through rework_requested" can't be
computed correctly from current status alone — an invoice that was
reworked and then re-sent (status now 'sent' or 'paid') would be
silently undercounted. Denormalized boolean marker, set once by
mark_rework_requested and never reset, rather than a full status-history
table this KPI doesn't otherwise need.

Revision ID: 0026
Revises: 0025
Create Date: 2026-08-24
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE invoices ADD COLUMN was_reworked BOOLEAN NOT NULL DEFAULT false")


def downgrade() -> None:
    op.execute("ALTER TABLE invoices DROP COLUMN IF EXISTS was_reworked")
