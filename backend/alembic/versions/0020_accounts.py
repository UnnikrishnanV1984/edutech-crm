"""accounts — B2B organization a deal is sold to. Standard tenant-scoped
pattern (DATABASE_SCHEMA.md §2). PIPELINE_AND_REVENUE_PLAN.md §4.1.

Revision ID: 0020
Revises: 0019
Create Date: 2026-08-24
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE accounts (
            id          UUID NOT NULL DEFAULT gen_random_uuid(),
            tenant_id   UUID NOT NULL REFERENCES tenants(id),
            name        TEXT NOT NULL,
            owner_id    UUID NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (id, tenant_id),
            FOREIGN KEY (owner_id, tenant_id) REFERENCES users (id, tenant_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_accounts_tenant_owner ON accounts (tenant_id, owner_id, created_at DESC)"
    )
    op.execute("ALTER TABLE accounts ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE accounts FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_accounts ON accounts
            USING (tenant_id = current_setting('app.tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS accounts")
