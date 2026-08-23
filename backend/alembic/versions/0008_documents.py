"""documents table

s3_key is computed server-side from tenant_id + contact_id
({tenant_id}/{contact_id}/{uuid}-{filename}) — never accepted from the
client (PHASE_1_PLAN.md §6). deal_id gets a composite FK for consistency
with every other optional deal_id column this phase (tasks), even though
PHASE_1_PLAN.md §4.7's DDL sketch omitted it — applying the plan's own
general rule (every FK is composite, §4/§6) over an inconsistency in one
table's shorthand listing.

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-24
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE documents (
            id           UUID NOT NULL DEFAULT gen_random_uuid(),
            tenant_id    UUID NOT NULL REFERENCES tenants(id),
            contact_id   UUID NOT NULL,
            deal_id      UUID,
            filename     TEXT NOT NULL,
            content_type TEXT NOT NULL,
            size_bytes   BIGINT NOT NULL,
            s3_key       TEXT NOT NULL,
            uploaded_by  UUID NOT NULL,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (id, tenant_id),
            FOREIGN KEY (contact_id, tenant_id) REFERENCES contacts (id, tenant_id),
            FOREIGN KEY (deal_id, tenant_id) REFERENCES deals (id, tenant_id),
            FOREIGN KEY (uploaded_by, tenant_id) REFERENCES users (id, tenant_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_documents_tenant_contact "
        "ON documents (tenant_id, contact_id, created_at DESC)"
    )
    op.execute("CREATE UNIQUE INDEX uq_documents_tenant_s3_key ON documents (tenant_id, s3_key)")
    op.execute("ALTER TABLE documents ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE documents FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_documents ON documents
            USING (tenant_id = current_setting('app.tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS documents")
