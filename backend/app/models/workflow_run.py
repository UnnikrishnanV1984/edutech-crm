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


class WorkflowRun(Base):
    """Hash-partitioned (alembic 0014) — same parent-table-only query
    pattern as app/models/activity.py's own partitioned table.
    workflow_rule_id IS a composite FK here (unlike escalations'
    sla_state_id/workflow_run_id) since workflow_rules itself isn't
    partitioned — no technical obstacle to it, so the general "every FK
    is composite" rule applies normally."""

    __tablename__ = "workflow_runs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workflow_rule_id", "tenant_id"], ["workflow_rules.id", "workflow_rules.tenant_id"]
        ),
        CheckConstraint(
            "trigger_source_type IN ('deal', 'task', 'contact')",
            name="ck_workflow_runs_trigger_source_type",
        ),
        CheckConstraint(
            "status IN ('success', 'failed', 'retrying', 'skipped_unavailable')",
            name="ck_workflow_runs_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), primary_key=True
    )
    workflow_rule_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    trigger_source_type: Mapped[str] = mapped_column(String, nullable=False)
    trigger_source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
