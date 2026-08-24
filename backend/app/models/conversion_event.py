import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ConversionEvent(Base):
    """One row per (deal, platform) — ARCHITECTURE.md §7d,
    PHASE_4B_CONVERSIONS_PLAN.md §3.1. Unlike lead_source_connections,
    nothing needs to discover tenant_id from this table before tenant_id
    is known, so it gets the standard RLS policy, not that table's
    exemption."""

    __tablename__ = "conversion_events"
    __table_args__ = (
        ForeignKeyConstraint(["deal_id", "tenant_id"], ["deals.id", "deals.tenant_id"]),
        CheckConstraint("platform IN ('meta', 'google')", name="ck_conversion_events_platform"),
        CheckConstraint(
            "status IN ('pending', 'sent', 'failed')", name="ck_conversion_events_status"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), primary_key=True
    )
    deal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    platform: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_error: Mapped[str | None] = mapped_column(String, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
