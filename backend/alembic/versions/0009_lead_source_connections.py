"""lead_source_connections table

Second documented global RLS exemption alongside `tenants`
(DATABASE_SCHEMA.md §1) — a webhook has to look up `external_account_id`
to *discover* `tenant_id` in the first place, before `app.tenant_id` can
be set, so this table cannot itself be gated by a policy keyed on that
session variable. Every application-layer query against it (admin
connection-management routes, the webhook tenant-resolution path) must
therefore include an explicit `tenant_id` filter by hand — there is no
RLS safety net here, unlike every other table in this schema. See
PHASE_2_PLAN.md §3.

`access_token_encrypted`/`refresh_token_encrypted` are `pgp_sym_encrypt`d
(pgcrypto, already enabled by 0001) at the application layer, keyed by
`INTEGRATION_CREDENTIALS_KEY` — this migration only shapes the columns as
opaque BYTEA, encryption/decryption lives in app/core/crypto.py.

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-24
"""

import os
from collections.abc import Sequence

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    app_user = os.environ.get("POSTGRES_APP_USER", "crm_app")

    op.execute(
        """
        CREATE TABLE lead_source_connections (
            id                      UUID NOT NULL DEFAULT gen_random_uuid(),
            tenant_id               UUID NOT NULL REFERENCES tenants(id),
            source                  TEXT NOT NULL
                                    CHECK (source IN ('meta', 'google', 'whatsapp', 'web')),
            external_account_id     TEXT NOT NULL,
            access_token_encrypted  BYTEA,
            refresh_token_encrypted BYTEA,
            token_expires_at        TIMESTAMPTZ,
            last_synced_at          TIMESTAMPTZ,
            status                  TEXT NOT NULL DEFAULT 'active'
                                    CHECK (status IN ('active', 'disabled')),
            created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (id, tenant_id)
        )
        """
    )

    # Global, not tenant-scoped — this is the lookup a webhook uses to
    # *discover* tenant_id in the first place.
    op.execute(
        "CREATE UNIQUE INDEX uq_lead_source_connections_external "
        "ON lead_source_connections (source, external_account_id)"
    )
    op.execute(
        "CREATE INDEX idx_lead_source_connections_tenant "
        "ON lead_source_connections (tenant_id, source)"
    )

    # Deliberately NO RLS — see module docstring. crm_app gets the same
    # three verbs as every other table (no DELETE — disconnect is a
    # status flip, matching contacts/courses' soft-disable convention).
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE ON lead_source_connections TO {app_user}"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS lead_source_connections")
