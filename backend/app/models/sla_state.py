import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SlaState(Base):
    """Hash-partitioned (alembic 0012) — maps to the sla_states parent
    table the same way app/models/activity.py already documents for its
    own partitioned table; the ORM doesn't need to know about
    partitioning. Written only by app/workers/sla.py's periodic
    computation, never by a request handler."""

    __tablename__ = "sla_states"
    __table_args__ = (
        ForeignKeyConstraint(
            ["sla_policy_id", "tenant_id"], ["sla_policies.id", "sla_policies.tenant_id"]
        ),
        ForeignKeyConstraint(["deal_id", "tenant_id"], ["deals.id", "deals.tenant_id"]),
        ForeignKeyConstraint(["task_id", "tenant_id"], ["tasks.id", "tasks.tenant_id"]),
        CheckConstraint(
            "state IN ('on_track', 'at_risk', 'breached')", name="ck_sla_states_state"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), primary_key=True
    )
    sla_policy_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    deal_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    task_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    target_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    warning_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    state: Mapped[str] = mapped_column(String, nullable=False, server_default="on_track")
    breached_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
