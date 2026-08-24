"""audit_logs — append-only config/lifecycle change history for Admin
visibility. DATABASE_SCHEMA.md §1 already listed this table as future
work ("not yet built; no phase has claimed it") — this is that build,
scoped to v1: write-only, no read API/UI yet (GAP_FIXES_PLAN.md item 6).

entity_id has no FK, same reasoning DATABASE_SCHEMA.md already documents
for escalations.sla_state_id/workflow_run_id: entity_type varies (user,
deal, escalation, ...), which Postgres can't express as one composite FK.

Not hash-partitioned in v1 — audit events are far lower-volume than
activities/sla_states/workflow_runs; revisit if that assumption turns out
wrong.

Revision ID: 0017
Revises: 0016
Create Date: 2026-08-24
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE audit_logs (
            id          UUID NOT NULL DEFAULT gen_random_uuid(),
            tenant_id   UUID NOT NULL REFERENCES tenants(id),
            actor_id    UUID NOT NULL,
            event_type  TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id   UUID NOT NULL,
            payload     JSONB,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (id, tenant_id),
            FOREIGN KEY (actor_id, tenant_id) REFERENCES users (id, tenant_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_audit_logs_tenant_entity "
        "ON audit_logs (tenant_id, entity_type, entity_id, created_at DESC)"
    )
    op.execute("ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audit_logs FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_audit_logs ON audit_logs
            USING (tenant_id = current_setting('app.tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS audit_logs")
