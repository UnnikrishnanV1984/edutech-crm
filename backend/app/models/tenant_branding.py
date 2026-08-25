import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TenantBranding(Base):
    """One row per tenant (enforced by a unique index, not the PK — see
    alembic 0029, same pattern as tenant_sla_settings). This is the
    mutable *draft* (alembic 0030, BRANDING_FULL_SYSTEM_PLAN.md) — nothing
    here is live until a TenantBrandingVersion snapshot is published.
    No row means "no branding configured / nothing edited yet" at the
    service layer, not a DB default row."""

    __tablename__ = "tenant_branding"
    __table_args__ = (
        ForeignKeyConstraint(["updated_by", "tenant_id"], ["users.id", "users.tenant_id"]),
        CheckConstraint(
            "accent_color IS NULL OR accent_color ~ '^#[0-9a-fA-F]{6}$'",
            name="ck_tenant_branding_accent_color",
        ),
        CheckConstraint(
            "header_background IN ('light', 'dark', 'accent')",
            name="ck_tenant_branding_header_background",
        ),
        CheckConstraint(
            "typeface IN ('system', 'serif')",
            name="ck_tenant_branding_typeface",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), primary_key=True
    )
    logo_s3_key: Mapped[str | None] = mapped_column(String, nullable=True)
    header_image_s3_key: Mapped[str | None] = mapped_column(String, nullable=True)
    company_display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    favicon_s3_key: Mapped[str | None] = mapped_column(String, nullable=True)
    login_backdrop_s3_key: Mapped[str | None] = mapped_column(String, nullable=True)
    accent_color: Mapped[str | None] = mapped_column(String, nullable=True)
    header_background: Mapped[str] = mapped_column(String, nullable=False, server_default="light")
    typeface: Mapped[str] = mapped_column(String, nullable=False, server_default="system")
    custom_domain: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# Columns copied verbatim between a draft and a version snapshot in
# either direction (publish: draft -> version; restore: version -> draft)
# — the two models intentionally share this exact field set (published_by/
# published_at/version_number only exist on the version side).
BRANDING_SNAPSHOT_FIELDS = (
    "logo_s3_key",
    "header_image_s3_key",
    "company_display_name",
    "favicon_s3_key",
    "login_backdrop_s3_key",
    "accent_color",
    "header_background",
    "typeface",
    "custom_domain",
)


class TenantBrandingVersion(Base):
    """Write-once — INSERTed by publish, never UPDATEd. Same shape/spirit
    as PipelineStageDefaultSnapshot: a full snapshot of every draft field
    at publish time, not a diff. The row with the highest version_number
    for a tenant is what GET /api/v1/branding (the live app-shell read)
    actually returns."""

    __tablename__ = "tenant_branding_versions"
    __table_args__ = (
        ForeignKeyConstraint(["published_by", "tenant_id"], ["users.id", "users.tenant_id"]),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), primary_key=True
    )
    version_number: Mapped[int] = mapped_column(nullable=False)
    logo_s3_key: Mapped[str | None] = mapped_column(String, nullable=True)
    header_image_s3_key: Mapped[str | None] = mapped_column(String, nullable=True)
    company_display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    favicon_s3_key: Mapped[str | None] = mapped_column(String, nullable=True)
    login_backdrop_s3_key: Mapped[str | None] = mapped_column(String, nullable=True)
    accent_color: Mapped[str | None] = mapped_column(String, nullable=True)
    header_background: Mapped[str] = mapped_column(String, nullable=False)
    typeface: Mapped[str] = mapped_column(String, nullable=False)
    custom_domain: Mapped[str | None] = mapped_column(String, nullable=True)
    published_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
