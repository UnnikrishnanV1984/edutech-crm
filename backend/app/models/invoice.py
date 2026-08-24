import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Numeric,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

INVOICE_STATUSES = ("draft", "sent", "rework_requested", "paid", "cancelled")


class Invoice(Base):
    """Maps to the invoices parent table — hash-partitioned by tenant_id
    (alembic 0023), same as activities/sla_states/workflow_runs/documents.
    The ORM doesn't need to know about partitioning. PIPELINE_AND_REVENUE.md
    §2.4. status transitions: draft/rework_requested -> sent (client),
    -> cancelled (client), sent -> rework_requested (system, stage-entry
    hook only), sent -> paid (system, payments service only) — see
    app/services/invoice_service.py."""

    __tablename__ = "invoices"
    __table_args__ = (
        ForeignKeyConstraint(["deal_id", "tenant_id"], ["deals.id", "deals.tenant_id"]),
        CheckConstraint(
            "status IN ('draft', 'sent', 'rework_requested', 'paid', 'cancelled')",
            name="ck_invoices_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), primary_key=True
    )
    deal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    invoice_number: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="draft")
    was_reworked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    """Set once by invoice_service.mark_rework_requested, never reset —
    report_service's invoice-rework-rate KPI needs "ever reworked", not
    just "currently rework_requested" (an invoice reworked then re-sent
    would otherwise be silently undercounted). Migration 0026."""
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
