"""pipeline_stage_default_snapshots — PIPELINE_CONFIG_RESET_PLAN.md §4.1.

Per-tenant, RLS-protected (unlike pipeline_stage_templates — this is real
per-tenant data: each tenant's own provisioning-time baseline, not shared
platform content). Write-once: rows are only ever inserted, never updated —
a snapshot is a point-in-time capture, not a live-editable config.

Also backfills a snapshot for every existing tenant (§4.2) from the same
DEFAULT_STAGES list app/services/pipeline_stage_service.py already seeds a
brand-new tenant's initial 8 stages from — deliberately not each tenant's
own current (possibly already-edited) pipeline_stages, since "system-
defined default" reads as the platform's known-good baseline, not an
accidental freeze of whatever a tenant had drifted into by the time this
shipped. Flagged as a judgment call in the plan, not re-litigated here.

Revision ID: 0027
Revises: 0026
Create Date: 2026-08-25
"""

from collections.abc import Sequence

from sqlalchemy import text

from alembic import op

revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Mirrors pipeline_stage_service.DEFAULT_STAGES exactly (name, is_won,
# is_lost) — duplicated here deliberately, same as 0025's template seed
# duplicating PIPELINE_AND_REVENUE.md's table, so this migration doesn't
# depend on application code that could change out from under it later.
_DEFAULT_STAGES = [
    ("Inquiry", False, False),
    ("Contacted", False, False),
    ("Demo scheduled", False, False),
    ("Demo attended", False, False),
    ("Application submitted", False, False),
    ("Fee paid", False, False),
    ("Enrolled", True, False),
    ("Dropped", False, True),
]


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE pipeline_stage_default_snapshots (
            id                  UUID NOT NULL DEFAULT gen_random_uuid(),
            tenant_id           UUID NOT NULL REFERENCES tenants(id),
            name                TEXT NOT NULL,
            sort_order          INTEGER NOT NULL,
            is_won              BOOLEAN NOT NULL DEFAULT false,
            is_lost             BOOLEAN NOT NULL DEFAULT false,
            is_invoice_stage    BOOLEAN NOT NULL DEFAULT false,
            is_rework_stage     BOOLEAN NOT NULL DEFAULT false,
            win_probability_pct INTEGER NOT NULL DEFAULT 0,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (id, tenant_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_pipeline_stage_default_snapshots_tenant "
        "ON pipeline_stage_default_snapshots (tenant_id)"
    )
    op.execute("ALTER TABLE pipeline_stage_default_snapshots ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE pipeline_stage_default_snapshots FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_pipeline_stage_default_snapshots
            ON pipeline_stage_default_snapshots
            USING (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )

    # Backfill — crm_migrate is superuser/BYPASSRLS (confirmed live), so
    # this cross-tenant INSERT...SELECT runs without a per-tenant
    # set_config loop, same as any other migration-time data backfill.
    # Bound parameters, not string-built SQL (same fix already applied to
    # 0025's seed insert) — one parameterized INSERT per tenant lacking a
    # snapshot, looped in Python rather than one giant VALUES-list SQL
    # string, since the tenant set isn't known until migration time.
    connection = op.get_bind()
    tenant_ids = connection.execute(
        text(
            "SELECT id FROM tenants WHERE id NOT IN "
            "(SELECT DISTINCT tenant_id FROM pipeline_stage_default_snapshots)"
        )
    ).scalars().all()
    insert_stmt = text(
        "INSERT INTO pipeline_stage_default_snapshots "
        "(tenant_id, name, sort_order, is_won, is_lost) "
        "VALUES (:tenant_id, :name, :sort_order, :is_won, :is_lost)"
    )
    for tenant_id in tenant_ids:
        for sort_order, (name, is_won, is_lost) in enumerate(_DEFAULT_STAGES, start=1):
            connection.execute(
                insert_stmt,
                {
                    "tenant_id": tenant_id,
                    "name": name,
                    "sort_order": sort_order,
                    "is_won": is_won,
                    "is_lost": is_lost,
                },
            )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS pipeline_stage_default_snapshots")
