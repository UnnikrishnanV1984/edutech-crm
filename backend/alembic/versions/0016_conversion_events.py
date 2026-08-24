"""conversion_events table + lead_source_connections.conversion_target_id

Outbound Meta/Google conversion signals — design-approved in
ARCHITECTURE.md §7d, implemented per PHASE_4B_CONVERSIONS_PLAN.md §3.
Standard tenant-scoped pattern (DATABASE_SCHEMA.md §2): unlike
lead_source_connections, nothing needs to discover tenant_id from this
table before tenant_id is known (the caller — the deal stage-change
route, then the Celery task — always already has it), so this table
gets the normal RLS policy, not the lead_source_connections exemption.

The (tenant_id, deal_id, platform) unique index is both the natural key
(one row per deal per platform) and the idempotency guard the
send_conversion_event task's _already_sent check relies on.

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-24
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE lead_source_connections ADD COLUMN conversion_target_id TEXT"
    )

    op.execute(
        """
        CREATE TABLE conversion_events (
            id          UUID NOT NULL DEFAULT gen_random_uuid(),
            tenant_id   UUID NOT NULL REFERENCES tenants(id),
            deal_id     UUID NOT NULL,
            platform    TEXT NOT NULL CHECK (platform IN ('meta', 'google')),
            status      TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'sent', 'failed')),
            attempts    INT NOT NULL DEFAULT 0,
            last_error  TEXT,
            sent_at     TIMESTAMPTZ,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (id, tenant_id),
            FOREIGN KEY (deal_id, tenant_id) REFERENCES deals (id, tenant_id)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_conversion_events_deal_platform "
        "ON conversion_events (tenant_id, deal_id, platform)"
    )
    op.execute(
        "CREATE INDEX idx_conversion_events_tenant_status "
        "ON conversion_events (tenant_id, status)"
    )
    op.execute("ALTER TABLE conversion_events ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE conversion_events FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_conversion_events ON conversion_events
            USING (tenant_id = current_setting('app.tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS conversion_events")
    op.execute(
        "ALTER TABLE lead_source_connections DROP COLUMN IF EXISTS conversion_target_id"
    )
