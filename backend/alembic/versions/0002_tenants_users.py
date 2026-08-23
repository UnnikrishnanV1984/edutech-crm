"""tenants and users tables

tenants is the one documented global exemption from the tenant_id/RLS
rule (DATABASE_SCHEMA.md §1) — reachable only by the tenant-resolution
path, never by a tenant-scoped request handler.

users follows the standard tenant-scoped pattern from DATABASE_SCHEMA.md
§2 exactly: tenant_id NOT NULL, tenant_id in the composite PK, a leading
composite index, RLS enabled AND forced, and a USING/WITH CHECK policy
keyed off current_setting('app.tenant_id') — the strict (non-two-arg)
form, which raises rather than silently returning NULL when the
session variable is unset (DEVELOPMENT_PLAN.md §3.3).

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-23
"""

import os
from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    app_user = os.environ.get("POSTGRES_APP_USER", "crm_app")

    op.execute(
        """
        CREATE TABLE tenants (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            slug        TEXT NOT NULL UNIQUE,
            name        TEXT NOT NULL,
            status      TEXT NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'suspended')),
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    # No RLS on tenants — it is the documented global exemption. crm_app
    # gets SELECT only: it resolves the caller's own tenant by id, never
    # lists or writes tenants.
    op.execute(f"GRANT SELECT ON tenants TO {app_user}")

    op.execute(
        """
        CREATE TABLE users (
            id            UUID NOT NULL DEFAULT gen_random_uuid(),
            tenant_id     UUID NOT NULL REFERENCES tenants(id),
            keycloak_sub  TEXT NOT NULL,
            email         TEXT NOT NULL,
            full_name     TEXT,
            role          TEXT NOT NULL
                          CHECK (role IN ('admin', 'manager', 'counselor')),
            status        TEXT NOT NULL DEFAULT 'active'
                          CHECK (status IN ('active', 'disabled')),
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (id, tenant_id)
        )
        """
    )

    op.execute(
        "CREATE INDEX idx_users_tenant_role "
        "ON users (tenant_id, role, created_at DESC)"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_users_tenant_keycloak_sub "
        "ON users (tenant_id, keycloak_sub)"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_users_tenant_email "
        "ON users (tenant_id, lower(email))"
    )

    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE users FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_users ON users
            USING (tenant_id = current_setting('app.tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS users")
    op.execute("DROP TABLE IF EXISTS tenants")
