"""pipeline_stages.win_probability_pct — admin-configurable, drives
stage-weighted forecasting (PHASE_4_PLAN.md §3.1). Defaults to 0 rather
than a guessed distribution — a tenant that hasn't configured
probabilities gets a 0 forecast, not a fabricated number nobody chose.

Revision ID: 0015
Revises: 0014
Create Date: 2026-08-24
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE pipeline_stages ADD COLUMN win_probability_pct INT NOT NULL DEFAULT 0"
    )
    op.execute(
        "ALTER TABLE pipeline_stages ADD CONSTRAINT ck_pipeline_stages_win_probability_pct "
        "CHECK (win_probability_pct BETWEEN 0 AND 100)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE pipeline_stages "
        "DROP CONSTRAINT IF EXISTS ck_pipeline_stages_win_probability_pct"
    )
    op.execute("ALTER TABLE pipeline_stages DROP COLUMN IF EXISTS win_probability_pct")
