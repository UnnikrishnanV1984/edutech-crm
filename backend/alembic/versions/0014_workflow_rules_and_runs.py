"""workflow_rules and workflow_runs — the latter hash-partitioned (high
write volume, DATABASE_SCHEMA.md §3), same pattern activities/sla_states
already use. See PHASE_3_PLAN.md §3.7/§3.8.

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-24
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE workflow_rules (
            id            UUID NOT NULL DEFAULT gen_random_uuid(),
            tenant_id     UUID NOT NULL REFERENCES tenants(id),
            name          TEXT NOT NULL,
            trigger_type  TEXT NOT NULL
                          CHECK (trigger_type IN
                              ('stage_changed', 'lead_created', 'task_overdue', 'elapsed_time')),
            trigger_config JSONB NOT NULL DEFAULT '{}',
            conditions    JSONB NOT NULL DEFAULT '[]',
            actions       JSONB NOT NULL DEFAULT '[]',
            status        TEXT NOT NULL DEFAULT 'draft'
                          CHECK (status IN ('draft', 'pending_approval', 'active', 'disabled')),
            created_by    UUID NOT NULL,
            approved_by   UUID NULL,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (id, tenant_id),
            FOREIGN KEY (created_by, tenant_id) REFERENCES users (id, tenant_id),
            FOREIGN KEY (approved_by, tenant_id) REFERENCES users (id, tenant_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_workflow_rules_tenant_status_trigger "
        "ON workflow_rules (tenant_id, status, trigger_type)"
    )
    op.execute("ALTER TABLE workflow_rules ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE workflow_rules FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_workflow_rules ON workflow_rules
            USING (tenant_id = current_setting('app.tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )

    op.execute(
        """
        CREATE TABLE workflow_runs (
            id                  UUID NOT NULL DEFAULT gen_random_uuid(),
            tenant_id           UUID NOT NULL REFERENCES tenants(id),
            workflow_rule_id    UUID NOT NULL,
            trigger_source_type TEXT NOT NULL
                                CHECK (trigger_source_type IN ('deal', 'task', 'contact')),
            trigger_source_id   UUID NOT NULL,
            status              TEXT NOT NULL
                                CHECK (status IN
                                    ('success', 'failed', 'retrying', 'skipped_unavailable')),
            attempt             INT NOT NULL DEFAULT 1,
            error_message       TEXT NULL,
            executed_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (id, tenant_id),
            FOREIGN KEY (workflow_rule_id, tenant_id)
                REFERENCES workflow_rules (id, tenant_id)
        ) PARTITION BY HASH (tenant_id)
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            FOR i IN 0..15 LOOP
                EXECUTE format(
                    'CREATE TABLE workflow_runs_p%s PARTITION OF workflow_runs
                        FOR VALUES WITH (MODULUS 16, REMAINDER %s);', i, i);
            END LOOP;
        END $$;
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_workflow_runs_dedupe "
        "ON workflow_runs (tenant_id, workflow_rule_id, trigger_source_type, trigger_source_id) "
        "WHERE status = 'success'"
    )
    op.execute(
        "CREATE INDEX idx_workflow_runs_tenant_rule "
        "ON workflow_runs (tenant_id, workflow_rule_id, executed_at DESC)"
    )
    op.execute("ALTER TABLE workflow_runs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE workflow_runs FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_workflow_runs ON workflow_runs
            USING (tenant_id = current_setting('app.tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS workflow_runs")
    op.execute("DROP TABLE IF EXISTS workflow_rules")
