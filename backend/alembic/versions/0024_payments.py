"""payments — hash-partitioned from creation, plain-UUID invoice_id
(escalations-style exception: invoices is itself hash-partitioned, per
0023, so a composite FK from here would reference a non-partition-key
column of a hash-partitioned table — same obstacle DATABASE_SCHEMA.md
already documents for escalations.sla_state_id/workflow_run_id). No FK
constraint on invoice_id at all; the service layer verifies tenant
ownership instead. PIPELINE_AND_REVENUE_PLAN.md §4.5.

Revision ID: 0024
Revises: 0023
Create Date: 2026-08-24
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE payments (
            id          UUID NOT NULL DEFAULT gen_random_uuid(),
            tenant_id   UUID NOT NULL REFERENCES tenants(id),
            invoice_id  UUID NOT NULL,
            amount      NUMERIC(12,2) NOT NULL,
            paid_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
            method      TEXT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (id, tenant_id)
        ) PARTITION BY HASH (tenant_id)
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            FOR i IN 0..15 LOOP
                EXECUTE format(
                    'CREATE TABLE payments_p%s PARTITION OF payments
                        FOR VALUES WITH (MODULUS 16, REMAINDER %s);', i, i);
            END LOOP;
        END $$;
        """
    )
    op.execute(
        "CREATE INDEX idx_payments_tenant_invoice ON payments (tenant_id, invoice_id, paid_at DESC)"
    )
    op.execute("ALTER TABLE payments ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE payments FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_payments ON payments
            USING (tenant_id = current_setting('app.tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS payments")
