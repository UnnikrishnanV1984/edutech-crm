import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Escalation(Base):
    """sla_state_id/workflow_run_id are plain UUID, not composite FKs —
    both reference hash-partitioned tables (PHASE_3_PLAN.md §3.5)."""

    __tablename__ = "escalations"
    __table_args__ = (
        ForeignKeyConstraint(["deal_id", "tenant_id"], ["deals.id", "deals.tenant_id"]),
        ForeignKeyConstraint(["task_id", "tenant_id"], ["tasks.id", "tasks.tenant_id"]),
        ForeignKeyConstraint(["raised_by", "tenant_id"], ["users.id", "users.tenant_id"]),
        ForeignKeyConstraint(["assigned_to", "tenant_id"], ["users.id", "users.tenant_id"]),
        CheckConstraint(
            "source IN ('sla_breach', 'workflow_failure', 'rule_triggered', 'manual')",
            name="ck_escalations_source",
        ),
        CheckConstraint(
            "status IN ('open', 'acknowledged', 'resolved', 'reassigned')",
            name="ck_escalations_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), primary_key=True
    )
    source: Mapped[str] = mapped_column(String, nullable=False)
    deal_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    task_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    sla_state_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    workflow_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    raised_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    assigned_to: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="open")
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(String, nullable=True)
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
