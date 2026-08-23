"""tenant_sla_settings and sla_policies

Both follow DATABASE_SCHEMA.md §2's standard pattern exactly, including
tenant_sla_settings despite being conceptually one row per tenant — that
doc's own instruction is "copy this pattern... do not deviate," so the
one-row-per-tenant constraint is a unique index, not a different PK
shape. See PHASE_3_PLAN.md §3.2/§3.3.

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-24
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE tenant_sla_settings (
            id             UUID NOT NULL DEFAULT gen_random_uuid(),
            tenant_id      UUID NOT NULL REFERENCES tenants(id),
            timezone       TEXT NOT NULL DEFAULT 'UTC',
            business_hours JSONB NOT NULL DEFAULT
                '{"mon":[["09:00","18:00"]],"tue":[["09:00","18:00"]],"wed":[["09:00","18:00"]],
                  "thu":[["09:00","18:00"]],"fri":[["09:00","18:00"]],"sat":[],"sun":[]}',
            holidays       JSONB NOT NULL DEFAULT '[]',
            created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (id, tenant_id)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_tenant_sla_settings_tenant ON tenant_sla_settings (tenant_id)"
    )
    op.execute("ALTER TABLE tenant_sla_settings ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenant_sla_settings FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_tenant_sla_settings ON tenant_sla_settings
            USING (tenant_id = current_setting('app.tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )

    op.execute(
        """
        CREATE TABLE sla_policies (
            id              UUID NOT NULL DEFAULT gen_random_uuid(),
            tenant_id       UUID NOT NULL REFERENCES tenants(id),
            name            TEXT NOT NULL,
            applies_to      TEXT NOT NULL CHECK (applies_to IN ('stage_entry', 'task_due')),
            stage_id        UUID NULL,
            task_type       TEXT NULL,
            target_minutes  INT NOT NULL CHECK (target_minutes > 0),
            warning_threshold_pct INT NOT NULL DEFAULT 80
                            CHECK (warning_threshold_pct BETWEEN 1 AND 99),
            status          TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'disabled')),
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (id, tenant_id),
            FOREIGN KEY (stage_id, tenant_id) REFERENCES pipeline_stages (id, tenant_id),
            CONSTRAINT ck_sla_policies_applies_to_fields CHECK (
                (applies_to = 'stage_entry' AND stage_id IS NOT NULL) OR
                (applies_to = 'task_due' AND stage_id IS NULL)
            )
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_sla_policies_tenant_applies_to ON sla_policies (tenant_id, applies_to)"
    )
    op.execute("ALTER TABLE sla_policies ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE sla_policies FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_sla_policies ON sla_policies
            USING (tenant_id = current_setting('app.tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS sla_policies")
    op.execute("DROP TABLE IF EXISTS tenant_sla_settings")
