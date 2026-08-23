"""tasks table

contact_id is required, deal_id optional (PHASE_1_PLAN.md §4.6) —
assignee_id is a composite FK to users, same rule as every other FK this
phase.

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-24
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE tasks (
            id            UUID NOT NULL DEFAULT gen_random_uuid(),
            tenant_id     UUID NOT NULL REFERENCES tenants(id),
            contact_id    UUID NOT NULL,
            deal_id       UUID,
            assignee_id   UUID NOT NULL,
            title         TEXT NOT NULL,
            description   TEXT,
            due_at        TIMESTAMPTZ,
            status        TEXT NOT NULL DEFAULT 'open'
                          CHECK (status IN ('open', 'done')),
            completed_at  TIMESTAMPTZ,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (id, tenant_id),
            FOREIGN KEY (contact_id, tenant_id) REFERENCES contacts (id, tenant_id),
            FOREIGN KEY (deal_id, tenant_id) REFERENCES deals (id, tenant_id),
            FOREIGN KEY (assignee_id, tenant_id) REFERENCES users (id, tenant_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_tasks_tenant_assignee_status_due "
        "ON tasks (tenant_id, assignee_id, status, due_at)"
    )
    op.execute(
        "CREATE INDEX idx_tasks_tenant_contact ON tasks (tenant_id, contact_id, created_at DESC)"
    )
    op.execute("ALTER TABLE tasks ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tasks FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_tasks ON tasks
            USING (tenant_id = current_setting('app.tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tasks")
