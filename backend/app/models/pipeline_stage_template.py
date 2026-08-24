import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PipelineStageTemplate(Base):
    """Global, platform-managed catalog — the `tenants`-style RLS
    exception (PIPELINE_AND_REVENUE.md §2.6): no `tenant_id` column at
    all, not just RLS skipped. GET-only API surface
    (app/api/pipeline_stage_templates.py) — never write this table from
    a tenant-facing request. Selecting a template copies its values into
    a tenant's own (RLS-protected) pipeline_stages row; nothing ever
    writes back here."""

    __tablename__ = "pipeline_stage_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    default_sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_won: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    is_lost: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    is_invoice_stage: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    is_rework_stage: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    default_win_probability_pct: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
