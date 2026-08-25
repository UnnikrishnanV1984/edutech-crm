"""escalations.snoozed_until / was_reopened — OPENFUNNEL_REBRAND_PLAN.md
Phase 7e, architect-approved (2026-08-25).

snoozed_until is nullable, only ever set alongside status='snoozed'; a
Celery Beat task (app/workers/escalations.py) flips it back to 'open' once
it passes, using Postgres's own now() rather than the app process's clock.

was_reopened is a denormalized boolean set once when an escalation is
reassigned and never reset — same shape as invoices.was_reworked
(migration 0026). Needed because the existing reassign handler already
clears acknowledged_at back to NULL on reassignment, so there is no way to
reconstruct "was this ever reopened" from the other columns after the
fact.

Revision ID: 0028
Revises: 0027
Create Date: 2026-08-25
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE escalations ADD COLUMN snoozed_until TIMESTAMPTZ NULL")
    op.execute(
        "ALTER TABLE escalations ADD COLUMN was_reopened BOOLEAN NOT NULL DEFAULT false"
    )
    op.execute("ALTER TABLE escalations DROP CONSTRAINT escalations_status_check")
    op.execute(
        "ALTER TABLE escalations ADD CONSTRAINT escalations_status_check "
        "CHECK (status IN ('open', 'acknowledged', 'resolved', 'reassigned', 'snoozed'))"
    )
    # Leads with tenant_id per the standard indexing rule; partial so it
    # only covers the (small) currently-snoozed slice, serving
    # app/workers/escalations.py's per-tenant expiry scan.
    op.execute(
        "CREATE INDEX idx_escalations_snoozed_until ON escalations (tenant_id, snoozed_until) "
        "WHERE status = 'snoozed'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_escalations_snoozed_until")
    op.execute("ALTER TABLE escalations DROP CONSTRAINT IF EXISTS escalations_status_check")
    op.execute(
        "ALTER TABLE escalations ADD CONSTRAINT escalations_status_check "
        "CHECK (status IN ('open', 'acknowledged', 'resolved', 'reassigned'))"
    )
    op.execute("ALTER TABLE escalations DROP COLUMN IF EXISTS was_reopened")
    op.execute("ALTER TABLE escalations DROP COLUMN IF EXISTS snoozed_until")
