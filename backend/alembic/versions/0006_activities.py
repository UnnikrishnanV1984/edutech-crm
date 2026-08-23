"""activities table — hash-partitioned per DATABASE_SCHEMA.md §3

Same 16-partition pattern as that doc's example, extended with deal_id
(nullable — not every future activity type will be deal-scoped) and
actor_id per PHASE_1_PLAN.md §4.5. RLS defined on the partitioned
(parent) table applies uniformly to every partition when queried through
the parent name, which is the only way application code ever queries
it — no per-partition RLS setup needed.

Phase 1 writes exactly one activity type: deal_stage_changed (step 9).
Logging other event types is a natural extension, not required for this
phase's exit criteria — don't add more writers without being asked.

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-24
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE activities (
            id          UUID NOT NULL DEFAULT gen_random_uuid(),
            tenant_id   UUID NOT NULL REFERENCES tenants(id),
            contact_id  UUID NOT NULL,
            deal_id     UUID,
            type        TEXT NOT NULL,
            actor_id    UUID NOT NULL,
            payload     JSONB,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (id, tenant_id),
            FOREIGN KEY (contact_id, tenant_id) REFERENCES contacts (id, tenant_id),
            FOREIGN KEY (deal_id, tenant_id) REFERENCES deals (id, tenant_id),
            FOREIGN KEY (actor_id, tenant_id) REFERENCES users (id, tenant_id)
        ) PARTITION BY HASH (tenant_id)
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            FOR i IN 0..15 LOOP
                EXECUTE format(
                    'CREATE TABLE activities_p%s PARTITION OF activities
                        FOR VALUES WITH (MODULUS 16, REMAINDER %s);', i, i);
            END LOOP;
        END $$;
        """
    )

    op.execute(
        "CREATE INDEX idx_activities_tenant_contact "
        "ON activities (tenant_id, contact_id, created_at DESC)"
    )
    op.execute("ALTER TABLE activities ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE activities FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_activities ON activities
            USING (tenant_id = current_setting('app.tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS activities")
