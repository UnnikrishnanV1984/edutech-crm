import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WorkflowRule(Base):
    __tablename__ = "workflow_rules"
    __table_args__ = (
        ForeignKeyConstraint(["created_by", "tenant_id"], ["users.id", "users.tenant_id"]),
        ForeignKeyConstraint(["approved_by", "tenant_id"], ["users.id", "users.tenant_id"]),
        CheckConstraint(
            "trigger_type IN ('stage_changed', 'lead_created', 'task_overdue', 'elapsed_time')",
            name="ck_workflow_rules_trigger_type",
        ),
        CheckConstraint(
            "status IN ('draft', 'pending_approval', 'active', 'disabled')",
            name="ck_workflow_rules_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), primary_key=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    trigger_type: Mapped[str] = mapped_column(String, nullable=False)
    trigger_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    conditions: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    actions: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="draft")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
