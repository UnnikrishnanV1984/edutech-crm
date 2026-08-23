import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FollowUpFlag(Base):
    __tablename__ = "follow_up_flags"
    __table_args__ = (
        ForeignKeyConstraint(["manager_id", "tenant_id"], ["users.id", "users.tenant_id"]),
        ForeignKeyConstraint(["deal_id", "tenant_id"], ["deals.id", "deals.tenant_id"]),
        ForeignKeyConstraint(["contact_id", "tenant_id"], ["contacts.id", "contacts.tenant_id"]),
        CheckConstraint(
            "(deal_id IS NOT NULL)::int + (contact_id IS NOT NULL)::int = 1",
            name="ck_follow_up_flags_target",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), primary_key=True
    )
    manager_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    deal_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    contact_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    note: Mapped[str] = mapped_column(String, nullable=False)
    remind_on: Mapped[date] = mapped_column(Date, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
