"""deals table

Standard tenant-scoped pattern. Every FK is composite — (contact_id,
tenant_id), (course_id, tenant_id), (stage_id, tenant_id), (owner_id,
tenant_id) — each referencing the target table's (id, tenant_id), per
PHASE_1_PLAN.md §4/§6. stage_changed_at is tracked from day one even
though per-stage SLA alerting is Phase 3 work — cheap now, avoids a
migration later when that phase needs it (PHASE_1_PLAN.md §4.4).

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-24
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE deals (
            id               UUID NOT NULL DEFAULT gen_random_uuid(),
            tenant_id        UUID NOT NULL REFERENCES tenants(id),
            contact_id       UUID NOT NULL,
            course_id        UUID NOT NULL,
            stage_id         UUID NOT NULL,
            owner_id         UUID NOT NULL,
            stage_changed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (id, tenant_id),
            FOREIGN KEY (contact_id, tenant_id) REFERENCES contacts (id, tenant_id),
            FOREIGN KEY (course_id, tenant_id) REFERENCES courses (id, tenant_id),
            FOREIGN KEY (stage_id, tenant_id) REFERENCES pipeline_stages (id, tenant_id),
            FOREIGN KEY (owner_id, tenant_id) REFERENCES users (id, tenant_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_deals_tenant_stage ON deals (tenant_id, stage_id, created_at DESC)"
    )
    op.execute("CREATE INDEX idx_deals_tenant_contact ON deals (tenant_id, contact_id)")
    op.execute("CREATE INDEX idx_deals_tenant_owner_stage ON deals (tenant_id, owner_id, stage_id)")
    op.execute("ALTER TABLE deals ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE deals FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_deals ON deals
            USING (tenant_id = current_setting('app.tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS deals")
