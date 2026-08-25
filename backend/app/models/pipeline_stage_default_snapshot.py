import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PipelineStageDefaultSnapshot(Base):
    """A tenant's own pipeline_stages, captured once at the moment
    ensure_default_stages first seeded them (pipeline_stage_service.py) —
    the "Reset to Default" baseline (PIPELINE_CONFIG_RESET_PLAN.md §4.1).
    RLS-protected like any other per-tenant table, unlike
    pipeline_stage_templates (that one's genuinely global content; this
    one is a tenant-specific snapshot). Write-once: nothing ever UPDATEs
    a row here, only INSERTs it once, ever, per tenant."""

    __tablename__ = "pipeline_stage_default_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), primary_key=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_won: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    is_lost: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    is_invoice_stage: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    is_rework_stage: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    win_probability_pct: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
