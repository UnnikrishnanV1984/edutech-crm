"""invoices — hash-partitioned from creation (architect review:
per-stage-transition transactional table, same shape as activities/
workflow_runs, avoiding the documents-style costly retrofit). Composite
FK to deals — deals isn't partitioned, so no obstacle, same as
workflow_runs.workflow_rule_id. PIPELINE_AND_REVENUE_PLAN.md §4.4.

Revision ID: 0023
Revises: 0022
Create Date: 2026-08-24
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE invoices (
            id             UUID NOT NULL DEFAULT gen_random_uuid(),
            tenant_id      UUID NOT NULL REFERENCES tenants(id),
            deal_id        UUID NOT NULL,
            invoice_number TEXT NOT NULL,
            amount         NUMERIC(12,2) NOT NULL,
            status         TEXT NOT NULL DEFAULT 'draft'
                           CHECK (status IN ('draft','sent','rework_requested','paid','cancelled')),
            issued_at      TIMESTAMPTZ NULL,
            due_date       DATE NULL,
            created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (id, tenant_id),
            FOREIGN KEY (deal_id, tenant_id) REFERENCES deals (id, tenant_id)
        ) PARTITION BY HASH (tenant_id)
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            FOR i IN 0..15 LOOP
                EXECUTE format(
                    'CREATE TABLE invoices_p%s PARTITION OF invoices
                        FOR VALUES WITH (MODULUS 16, REMAINDER %s);', i, i);
            END LOOP;
        END $$;
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_invoices_tenant_number ON invoices (tenant_id, invoice_number)"
    )
    op.execute(
        "CREATE INDEX idx_invoices_tenant_deal ON invoices (tenant_id, deal_id, created_at DESC)"
    )
    op.execute("ALTER TABLE invoices ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE invoices FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_invoices ON invoices
            USING (tenant_id = current_setting('app.tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS invoices")
