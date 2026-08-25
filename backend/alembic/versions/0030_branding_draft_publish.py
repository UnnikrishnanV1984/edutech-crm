"""tenant_branding gains draft fields + tenant_branding_versions —
BRANDING_FULL_SYSTEM_PLAN.md, architect-approved 2026-08-26.

tenant_branding (already in production, migration 0029) becomes
explicitly the mutable *draft*: adds company_display_name, favicon_s3_key,
login_backdrop_s3_key, accent_color, header_background, typeface,
custom_domain. GET /api/v1/branding (the live app-shell read) stops
reading this table directly and starts reading the latest row of the new
tenant_branding_versions table instead — nothing here changes what's
"live" until a Publish action inserts the first version row.

tenant_branding_versions is write-once (INSERT-only, never UPDATEd) — same
shape/spirit as pipeline_stage_default_snapshots (migration 0022-ish):
a full snapshot of every draft column at publish time, not a diff.
Architect note: kept tenant_branding's name as-is rather than renaming to
tenant_branding_draft — this repo already has the same "current working
copy keeps its plain name, snapshot-history table gets the qualifier"
relationship between pipeline_stages and pipeline_stage_default_snapshots,
so this isn't a new naming convention being introduced.

Revision ID: 0030
Revises: 0029
Create Date: 2026-08-26
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0030"
down_revision: str | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE tenant_branding ADD COLUMN company_display_name TEXT NULL")
    op.execute("ALTER TABLE tenant_branding ADD COLUMN favicon_s3_key TEXT NULL")
    op.execute("ALTER TABLE tenant_branding ADD COLUMN login_backdrop_s3_key TEXT NULL")
    op.execute(
        "ALTER TABLE tenant_branding ADD COLUMN accent_color TEXT NULL "
        "CHECK (accent_color IS NULL OR accent_color ~ '^#[0-9a-fA-F]{6}$')"
    )
    op.execute(
        "ALTER TABLE tenant_branding ADD COLUMN header_background TEXT NOT NULL DEFAULT 'light' "
        "CHECK (header_background IN ('light', 'dark', 'accent'))"
    )
    op.execute(
        "ALTER TABLE tenant_branding ADD COLUMN typeface TEXT NOT NULL DEFAULT 'system' "
        "CHECK (typeface IN ('system', 'serif'))"
    )
    op.execute("ALTER TABLE tenant_branding ADD COLUMN custom_domain TEXT NULL")

    op.execute(
        """
        CREATE TABLE tenant_branding_versions (
            id                     UUID NOT NULL DEFAULT gen_random_uuid(),
            tenant_id              UUID NOT NULL REFERENCES tenants(id),
            version_number         INTEGER NOT NULL,
            logo_s3_key            TEXT NULL,
            header_image_s3_key    TEXT NULL,
            company_display_name   TEXT NULL,
            favicon_s3_key         TEXT NULL,
            login_backdrop_s3_key  TEXT NULL,
            accent_color           TEXT NULL,
            header_background      TEXT NOT NULL,
            typeface               TEXT NOT NULL,
            custom_domain          TEXT NULL,
            published_by           UUID NOT NULL,
            published_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (id, tenant_id),
            FOREIGN KEY (published_by, tenant_id) REFERENCES users (id, tenant_id),
            UNIQUE (tenant_id, version_number)
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_tenant_branding_versions_tenant_version "
        "ON tenant_branding_versions (tenant_id, version_number DESC)"
    )
    op.execute("ALTER TABLE tenant_branding_versions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenant_branding_versions FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_tenant_branding_versions ON tenant_branding_versions
            USING (tenant_id = current_setting('app.tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tenant_branding_versions")
    op.execute("ALTER TABLE tenant_branding DROP COLUMN IF EXISTS custom_domain")
    op.execute("ALTER TABLE tenant_branding DROP COLUMN IF EXISTS typeface")
    op.execute("ALTER TABLE tenant_branding DROP COLUMN IF EXISTS header_background")
    op.execute("ALTER TABLE tenant_branding DROP COLUMN IF EXISTS accent_color")
    op.execute("ALTER TABLE tenant_branding DROP COLUMN IF EXISTS login_backdrop_s3_key")
    op.execute("ALTER TABLE tenant_branding DROP COLUMN IF EXISTS favicon_s3_key")
    op.execute("ALTER TABLE tenant_branding DROP COLUMN IF EXISTS company_display_name")
