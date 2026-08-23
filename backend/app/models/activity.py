import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, ForeignKeyConstraint, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Activity(Base):
    """Maps to the activities parent table — Postgres routes inserts to
    the right hash partition transparently; the ORM doesn't need to know
    about partitioning. Phase 1 only ever writes type='deal_stage_changed'
    (see services/activity_service.py)."""

    __tablename__ = "activities"
    __table_args__ = (
        ForeignKeyConstraint(["contact_id", "tenant_id"], ["contacts.id", "contacts.tenant_id"]),
        ForeignKeyConstraint(["deal_id", "tenant_id"], ["deals.id", "deals.tenant_id"]),
        ForeignKeyConstraint(["actor_id", "tenant_id"], ["users.id", "users.tenant_id"]),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), primary_key=True
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    deal_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    type: Mapped[str] = mapped_column(String, nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
