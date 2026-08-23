"""escalations and follow_up_flags

escalations.sla_state_id / workflow_run_id are plain UUID columns, not
composite FKs — Postgres can't cleanly express a FK into a
non-partition-key column of a hash-partitioned table here, and the
tenant_id match is already guaranteed by both rows sharing the same
computation/request. 'rule_triggered' is included in the source CHECK
from the start (a workflow rule's own raise_escalation action, distinct
from 'workflow_failure' — the rule itself erroring) rather than added in
a later migration. See PHASE_3_PLAN.md §3.5/§3.6/§7.4.

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-24
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE escalations (
            id                UUID NOT NULL DEFAULT gen_random_uuid(),
            tenant_id         UUID NOT NULL REFERENCES tenants(id),
            source            TEXT NOT NULL
                              CHECK (source IN
                                  ('sla_breach', 'workflow_failure', 'rule_triggered', 'manual')),
            deal_id           UUID NULL,
            task_id           UUID NULL,
            sla_state_id      UUID NULL,
            workflow_run_id   UUID NULL,
            raised_by         UUID NULL,
            assigned_to       UUID NOT NULL,
            status            TEXT NOT NULL DEFAULT 'open'
                              CHECK (status IN ('open', 'acknowledged', 'resolved', 'reassigned')),
            reason            TEXT NULL,
            resolution_note   TEXT NULL,
            opened_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
            acknowledged_at   TIMESTAMPTZ NULL,
            resolved_at       TIMESTAMPTZ NULL,
            PRIMARY KEY (id, tenant_id),
            FOREIGN KEY (deal_id, tenant_id) REFERENCES deals (id, tenant_id),
            FOREIGN KEY (task_id, tenant_id) REFERENCES tasks (id, tenant_id),
            FOREIGN KEY (raised_by, tenant_id) REFERENCES users (id, tenant_id),
            FOREIGN KEY (assigned_to, tenant_id) REFERENCES users (id, tenant_id),
            CONSTRAINT ck_escalations_source_fields CHECK (
                (source = 'sla_breach' AND sla_state_id IS NOT NULL) OR
                (source IN ('workflow_failure', 'rule_triggered')
                    AND workflow_run_id IS NOT NULL) OR
                (source = 'manual' AND raised_by IS NOT NULL)
            )
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_escalations_tenant_status "
        "ON escalations (tenant_id, status, opened_at DESC)"
    )
    op.execute(
        "CREATE INDEX idx_escalations_tenant_assigned "
        "ON escalations (tenant_id, assigned_to, status)"
    )
    op.execute("ALTER TABLE escalations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE escalations FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_escalations ON escalations
            USING (tenant_id = current_setting('app.tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )

    op.execute(
        """
        CREATE TABLE follow_up_flags (
            id          UUID NOT NULL DEFAULT gen_random_uuid(),
            tenant_id   UUID NOT NULL REFERENCES tenants(id),
            manager_id  UUID NOT NULL,
            deal_id     UUID NULL,
            contact_id  UUID NULL,
            note        TEXT NOT NULL,
            remind_on   DATE NOT NULL,
            resolved_at TIMESTAMPTZ NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (id, tenant_id),
            FOREIGN KEY (manager_id, tenant_id) REFERENCES users (id, tenant_id),
            FOREIGN KEY (deal_id, tenant_id) REFERENCES deals (id, tenant_id),
            FOREIGN KEY (contact_id, tenant_id) REFERENCES contacts (id, tenant_id),
            CONSTRAINT ck_follow_up_flags_target CHECK (
                (deal_id IS NOT NULL)::int + (contact_id IS NOT NULL)::int = 1
            )
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_follow_up_flags_tenant_manager "
        "ON follow_up_flags (tenant_id, manager_id, remind_on)"
    )
    op.execute("ALTER TABLE follow_up_flags ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE follow_up_flags FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_follow_up_flags ON follow_up_flags
            USING (tenant_id = current_setting('app.tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS follow_up_flags")
    op.execute("DROP TABLE IF EXISTS escalations")
