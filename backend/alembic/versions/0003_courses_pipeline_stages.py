"""courses and pipeline_stages tables

Both follow the standard tenant-scoped pattern from DATABASE_SCHEMA.md §2:
tenant_id in the composite PK, a leading composite index, RLS enabled and
forced, and a policy on the strict current_setting('app.tenant_id')::uuid
form (raises rather than silently returning NULL when unset — matches
0002's convention).

pipeline_stages carries is_won/is_lost booleans (not a hardcoded stage
name) so Phase 4's forecasting/win-probability work has something stable
to read regardless of what a tenant calls its stages — see
PHASE_1_PLAN.md §4.2.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-24
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE courses (
            id          UUID NOT NULL DEFAULT gen_random_uuid(),
            tenant_id   UUID NOT NULL REFERENCES tenants(id),
            name        TEXT NOT NULL,
            code        TEXT NOT NULL,
            status      TEXT NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'inactive')),
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (id, tenant_id)
        )
        """
    )
    op.execute("CREATE UNIQUE INDEX uq_courses_tenant_code ON courses (tenant_id, code)")
    op.execute(
        "CREATE INDEX idx_courses_tenant_status "
        "ON courses (tenant_id, status, created_at DESC)"
    )
    op.execute("ALTER TABLE courses ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE courses FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_courses ON courses
            USING (tenant_id = current_setting('app.tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )

    op.execute(
        """
        CREATE TABLE pipeline_stages (
            id           UUID NOT NULL DEFAULT gen_random_uuid(),
            tenant_id    UUID NOT NULL REFERENCES tenants(id),
            name         TEXT NOT NULL,
            sort_order   INTEGER NOT NULL,
            is_won       BOOLEAN NOT NULL DEFAULT false,
            is_lost      BOOLEAN NOT NULL DEFAULT false,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (id, tenant_id)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_pipeline_stages_tenant_name ON pipeline_stages (tenant_id, name)"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_pipeline_stages_tenant_sort_order "
        "ON pipeline_stages (tenant_id, sort_order)"
    )
    op.execute(
        "CREATE INDEX idx_pipeline_stages_tenant_sort "
        "ON pipeline_stages (tenant_id, sort_order)"
    )
    op.execute("ALTER TABLE pipeline_stages ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE pipeline_stages FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_pipeline_stages ON pipeline_stages
            USING (tenant_id = current_setting('app.tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS pipeline_stages")
    op.execute("DROP TABLE IF EXISTS courses")
