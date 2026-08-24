import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PipelineStage(Base):
    """is_won/is_lost carry the fixed meaning, not the (tenant-editable)
    name — see PHASE_1_PLAN.md §4.2."""

    __tablename__ = "pipeline_stages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), primary_key=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_won: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    is_lost: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    win_probability_pct: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    """Admin-configurable, drives stage-weighted forecasting
    (PHASE_4_PLAN.md §3.1) — 0 until an admin sets it, not a guessed
    default."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
