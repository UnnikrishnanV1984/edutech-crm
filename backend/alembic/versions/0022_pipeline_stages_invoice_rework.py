"""pipeline_stages — is_invoice_stage/is_rework_stage, extending the
existing is_won/is_lost fixed-flag pattern (architect-confirmed over a
stage_type enum at this scale). PIPELINE_AND_REVENUE_PLAN.md §4.3.

Revision ID: 0022
Revises: 0021
Create Date: 2026-08-24
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE pipeline_stages ADD COLUMN is_invoice_stage BOOLEAN NOT NULL DEFAULT false"
    )
    op.execute(
        "ALTER TABLE pipeline_stages ADD COLUMN is_rework_stage BOOLEAN NOT NULL DEFAULT false"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE pipeline_stages DROP COLUMN IF EXISTS is_rework_stage")
    op.execute("ALTER TABLE pipeline_stages DROP COLUMN IF EXISTS is_invoice_stage")
