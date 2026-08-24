import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, ForeignKeyConstraint, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Deal(Base):
    __tablename__ = "deals"
    __table_args__ = (
        ForeignKeyConstraint(["contact_id", "tenant_id"], ["contacts.id", "contacts.tenant_id"]),
        ForeignKeyConstraint(["course_id", "tenant_id"], ["courses.id", "courses.tenant_id"]),
        ForeignKeyConstraint(
            ["stage_id", "tenant_id"], ["pipeline_stages.id", "pipeline_stages.tenant_id"]
        ),
        ForeignKeyConstraint(["owner_id", "tenant_id"], ["users.id", "users.tenant_id"]),
        ForeignKeyConstraint(["account_id", "tenant_id"], ["accounts.id", "accounts.tenant_id"]),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), primary_key=True
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    course_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    """Nullable — EdTech-specific, not every vertical this deal model now
    serves has a course (PIPELINE_AND_REVENUE.md §2.1)."""
    stage_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    account_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default="0")
    currency: Mapped[str] = mapped_column(String, nullable=False, server_default="INR")
    stage_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
