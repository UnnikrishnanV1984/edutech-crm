"""deals — value/currency, nullable account_id, course_id relaxed to
nullable. Additive/relaxing only, no backfill needed — confirmed safe
against the live 0005 schema during architect review.
PIPELINE_AND_REVENUE_PLAN.md §4.2.

Revision ID: 0021
Revises: 0020
Create Date: 2026-08-24
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE deals ADD COLUMN value NUMERIC(12,2) NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE deals ADD COLUMN currency TEXT NOT NULL DEFAULT 'INR'")
    op.execute("ALTER TABLE deals ADD COLUMN account_id UUID NULL")
    op.execute(
        "ALTER TABLE deals ADD CONSTRAINT deals_account_id_tenant_id_fkey "
        "FOREIGN KEY (account_id, tenant_id) REFERENCES accounts (id, tenant_id)"
    )
    op.execute("CREATE INDEX idx_deals_tenant_account ON deals (tenant_id, account_id)")
    op.execute("ALTER TABLE deals ALTER COLUMN course_id DROP NOT NULL")


def downgrade() -> None:
    # course_id NOT NULL is not restored — any deal created with a NULL
    # course_id while this migration was applied would break the
    # downgrade otherwise, and there's no sensible value to backfill it
    # with. Same call `documents_partition`'s downgrade makes for
    # dropped precision: best-effort schema reversion, not a guarantee
    # against data created under the new schema.
    op.execute("DROP INDEX IF EXISTS idx_deals_tenant_account")
    op.execute("ALTER TABLE deals DROP CONSTRAINT IF EXISTS deals_account_id_tenant_id_fkey")
    op.execute("ALTER TABLE deals DROP COLUMN IF EXISTS account_id")
    op.execute("ALTER TABLE deals DROP COLUMN IF EXISTS currency")
    op.execute("ALTER TABLE deals DROP COLUMN IF EXISTS value")
