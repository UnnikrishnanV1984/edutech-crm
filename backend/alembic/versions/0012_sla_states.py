"""sla_states — hash-partitioned (high write volume, DATABASE_SCHEMA.md
§3), the same pattern activities already uses. Computed periodically by
a Celery Beat task (app/workers/sla.py), never written by a request
handler directly. See PHASE_3_PLAN.md §3.4.

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-24
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE sla_states (
            id            UUID NOT NULL DEFAULT gen_random_uuid(),
            tenant_id     UUID NOT NULL REFERENCES tenants(id),
            sla_policy_id UUID NOT NULL,
            deal_id       UUID NULL,
            task_id       UUID NULL,
            target_at     TIMESTAMPTZ NOT NULL,
            warning_at    TIMESTAMPTZ NOT NULL,
            state         TEXT NOT NULL DEFAULT 'on_track'
                          CHECK (state IN ('on_track', 'at_risk', 'breached')),
            breached_at   TIMESTAMPTZ NULL,
            computed_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (id, tenant_id),
            FOREIGN KEY (sla_policy_id, tenant_id) REFERENCES sla_policies (id, tenant_id),
            FOREIGN KEY (deal_id, tenant_id) REFERENCES deals (id, tenant_id),
            FOREIGN KEY (task_id, tenant_id) REFERENCES tasks (id, tenant_id),
            CONSTRAINT ck_sla_states_exactly_one_target CHECK (
                (deal_id IS NOT NULL)::int + (task_id IS NOT NULL)::int = 1
            )
        ) PARTITION BY HASH (tenant_id)
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            FOR i IN 0..15 LOOP
                EXECUTE format(
                    'CREATE TABLE sla_states_p%s PARTITION OF sla_states
                        FOR VALUES WITH (MODULUS 16, REMAINDER %s);', i, i);
            END LOOP;
        END $$;
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_sla_states_policy_target "
        "ON sla_states (tenant_id, sla_policy_id, deal_id, task_id)"
    )
    op.execute(
        "CREATE INDEX idx_sla_states_tenant_state ON sla_states (tenant_id, state, target_at)"
    )
    op.execute("ALTER TABLE sla_states ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE sla_states FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_sla_states ON sla_states
            USING (tenant_id = current_setting('app.tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS sla_states")
