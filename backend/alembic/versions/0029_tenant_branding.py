"""tenant_branding — Configurations "Branding" tab (uploaded logo/header
image, applied immediately, no draft/publish workflow — a deliberately
smaller scope than the wireframe's full white-label system, per an
explicit product decision on 2026-08-25: no color/typeface pickers, no
login-screen theming, no version history for this pass).

Same one-row-per-tenant pattern as tenant_sla_settings (alembic 0011):
standard (id, tenant_id) composite PK + a unique index on tenant_id, not
a different PK shape. Asset bytes live in S3/MinIO (the same bucket
documents.py already uses) — this table only stores the s3_key, same
division of responsibility as the documents table.

Revision ID: 0029
Revises: 0028
Create Date: 2026-08-25
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0029"
down_revision: str | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE tenant_branding (
            id                   UUID NOT NULL DEFAULT gen_random_uuid(),
            tenant_id            UUID NOT NULL REFERENCES tenants(id),
            logo_s3_key          TEXT NULL,
            header_image_s3_key  TEXT NULL,
            updated_by           UUID NULL,
            updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (id, tenant_id),
            FOREIGN KEY (updated_by, tenant_id) REFERENCES users (id, tenant_id)
        )
        """
    )
    op.execute("CREATE UNIQUE INDEX uq_tenant_branding_tenant ON tenant_branding (tenant_id)")
    op.execute("ALTER TABLE tenant_branding ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenant_branding FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_tenant_branding ON tenant_branding
            USING (tenant_id = current_setting('app.tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tenant_branding")
