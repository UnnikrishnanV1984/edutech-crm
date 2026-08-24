"""documents — hash-partitioned like its high-volume siblings
(activities/sla_states/workflow_runs, alembic 0006/0012/0014). Was left
plain when created (0008) despite being a similarly tenant-scoped,
potentially high-row-count table — GAP_FIXES_PLAN.md item 7.

Postgres can't ALTER TABLE ... PARTITION BY an existing populated table
in place, unlike 0006/0012/0014 which had the luxury of partitioning
from CREATE TABLE before any data existed. This is a create-copy-swap:
build documents_new as the partitioned table, copy every row across,
drop the old table, rename the new one into place. No other table holds
a composite FK referencing documents(id, tenant_id) (confirmed by
search before writing this), so nothing else needs updating to point at
the renamed table — Postgres FK constraints referencing documents are
recreated fresh on documents_new itself instead.

Revision ID: 0019
Revises: 0018
Create Date: 2026-08-24
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE documents_new (
            id           UUID NOT NULL DEFAULT gen_random_uuid(),
            tenant_id    UUID NOT NULL CONSTRAINT documents_tenant_id_fkey REFERENCES tenants(id),
            contact_id   UUID NOT NULL,
            deal_id      UUID,
            filename     TEXT NOT NULL,
            content_type TEXT NOT NULL,
            size_bytes   BIGINT NOT NULL,
            s3_key       TEXT NOT NULL,
            uploaded_by  UUID NOT NULL,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT documents_pkey PRIMARY KEY (id, tenant_id),
            CONSTRAINT documents_contact_id_tenant_id_fkey
                FOREIGN KEY (contact_id, tenant_id) REFERENCES contacts (id, tenant_id),
            CONSTRAINT documents_deal_id_tenant_id_fkey
                FOREIGN KEY (deal_id, tenant_id) REFERENCES deals (id, tenant_id),
            CONSTRAINT documents_uploaded_by_tenant_id_fkey
                FOREIGN KEY (uploaded_by, tenant_id) REFERENCES users (id, tenant_id)
        ) PARTITION BY HASH (tenant_id)
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            FOR i IN 0..15 LOOP
                EXECUTE format(
                    'CREATE TABLE documents_new_p%s PARTITION OF documents_new
                        FOR VALUES WITH (MODULUS 16, REMAINDER %s);', i, i);
            END LOOP;
        END $$;
        """
    )

    op.execute(
        "INSERT INTO documents_new "
        "(id, tenant_id, contact_id, deal_id, filename, content_type, size_bytes, "
        " s3_key, uploaded_by, created_at) "
        "SELECT id, tenant_id, contact_id, deal_id, filename, content_type, size_bytes, "
        "       s3_key, uploaded_by, created_at "
        "FROM documents"
    )

    op.execute("DROP TABLE documents")
    op.execute("ALTER TABLE documents_new RENAME TO documents")
    op.execute(
        """
        DO $$
        BEGIN
            FOR i IN 0..15 LOOP
                EXECUTE format('ALTER TABLE documents_new_p%s RENAME TO documents_p%s;', i, i);
            END LOOP;
        END $$;
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
    op.execute(
        """
        CREATE TABLE documents_old (
            id           UUID NOT NULL DEFAULT gen_random_uuid(),
            tenant_id    UUID NOT NULL CONSTRAINT documents_tenant_id_fkey REFERENCES tenants(id),
            contact_id   UUID NOT NULL,
            deal_id      UUID,
            filename     TEXT NOT NULL,
            content_type TEXT NOT NULL,
            size_bytes   BIGINT NOT NULL,
            s3_key       TEXT NOT NULL,
            uploaded_by  UUID NOT NULL,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT documents_pkey PRIMARY KEY (id, tenant_id),
            CONSTRAINT documents_contact_id_tenant_id_fkey
                FOREIGN KEY (contact_id, tenant_id) REFERENCES contacts (id, tenant_id),
            CONSTRAINT documents_deal_id_tenant_id_fkey
                FOREIGN KEY (deal_id, tenant_id) REFERENCES deals (id, tenant_id),
            CONSTRAINT documents_uploaded_by_tenant_id_fkey
                FOREIGN KEY (uploaded_by, tenant_id) REFERENCES users (id, tenant_id)
        )
        """
    )
    op.execute(
        "INSERT INTO documents_old "
        "(id, tenant_id, contact_id, deal_id, filename, content_type, size_bytes, "
        " s3_key, uploaded_by, created_at) "
        "SELECT id, tenant_id, contact_id, deal_id, filename, content_type, size_bytes, "
        "       s3_key, uploaded_by, created_at "
        "FROM documents"
    )
    op.execute("DROP TABLE documents")
    op.execute("ALTER TABLE documents_old RENAME TO documents")

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
