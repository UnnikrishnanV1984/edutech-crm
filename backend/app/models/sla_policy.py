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


class SlaPolicy(Base):
    __tablename__ = "sla_policies"
    __table_args__ = (
        ForeignKeyConstraint(
            ["stage_id", "tenant_id"], ["pipeline_stages.id", "pipeline_stages.tenant_id"]
        ),
        CheckConstraint(
            "applies_to IN ('stage_entry', 'task_due')", name="ck_sla_policies_applies_to"
        ),
        CheckConstraint("status IN ('active', 'disabled')", name="ck_sla_policies_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), primary_key=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    applies_to: Mapped[str] = mapped_column(String, nullable=False)
    stage_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    task_type: Mapped[str | None] = mapped_column(String, nullable=True)
    target_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    warning_threshold_pct: Mapped[int] = mapped_column(Integer, nullable=False, server_default="80")
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
