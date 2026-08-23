"""contacts table

Standard tenant-scoped pattern. owner_id is a COMPOSITE foreign key to
users (id, tenant_id) — matching users' actual PK shape from 0002 — not a
bare owner_id -> users.id reference. RLS blocks a cross-tenant *read*;
only a composite FK stops a cross-tenant *link* at the constraint level
(PHASE_1_PLAN.md §4/§6 — this rule applies to every FK added this phase).

Dedupe (PHASE_1_PLAN.md §4.3) is two partial unique indexes — email and
phone are each optional, so a plain UNIQUE would incorrectly collide
every contact with no email/phone against every other one with no
email/phone. WHERE ... IS NOT NULL avoids that.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-24
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE contacts (
            id          UUID NOT NULL DEFAULT gen_random_uuid(),
            tenant_id   UUID NOT NULL REFERENCES tenants(id),
            full_name   TEXT NOT NULL,
            email       TEXT,
            phone       TEXT,
            lead_source TEXT NOT NULL
                        CHECK (lead_source IN ('meta', 'google', 'web', 'whatsapp', 'manual')),
            owner_id    UUID NOT NULL,
            status      TEXT NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'archived')),
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (id, tenant_id),
            FOREIGN KEY (owner_id, tenant_id) REFERENCES users (id, tenant_id)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_contacts_tenant_email "
        "ON contacts (tenant_id, lower(email)) WHERE email IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_contacts_tenant_phone "
        "ON contacts (tenant_id, phone) WHERE phone IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX idx_contacts_tenant_owner "
        "ON contacts (tenant_id, owner_id, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX idx_contacts_tenant_created "
        "ON contacts (tenant_id, created_at DESC)"
    )
    op.execute("ALTER TABLE contacts ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE contacts FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_contacts ON contacts
            USING (tenant_id = current_setting('app.tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS contacts")
