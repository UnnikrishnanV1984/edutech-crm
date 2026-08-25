import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, ForeignKeyConstraint, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TenantBranding(Base):
    """One row per tenant (enforced by a unique index, not the PK — see
    alembic 0029, same pattern as tenant_sla_settings). No row means "no
    branding configured" at the service layer, not a DB default row."""

    __tablename__ = "tenant_branding"
    __table_args__ = (
        ForeignKeyConstraint(["updated_by", "tenant_id"], ["users.id", "users.tenant_id"]),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), primary_key=True
    )
    logo_s3_key: Mapped[str | None] = mapped_column(String, nullable=True)
    header_image_s3_key: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
