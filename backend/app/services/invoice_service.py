"""Invoice status state machine — PIPELINE_AND_REVENUE_PLAN.md §5.4.

Client-triggerable transitions only go through update_invoice (validated
against _CLIENT_ALLOWED_TRANSITIONS, and InvoiceUpdate's own validator
already rejects any status value outside CLIENT_SETTABLE_STATUSES before
this is even reached). The two system-only transitions — entering
rework_requested (app/api/deals.py's rework-stage hook) and entering paid
(app/services/payment_service.py's paid-threshold check) — call
mark_rework_requested/mark_paid directly, bypassing the client-facing
validator entirely, same as escalation_service.py's split between
update_escalation (client-facing, validated) and
create_sla_breach_escalation (system-only, no validation needed since
the caller already controls the transition).
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import VALIDATION_ERROR, ApiError
from app.models.invoice import Invoice
from app.schemas.invoice import InvoiceCreate, InvoiceUpdate

_CLIENT_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"sent", "cancelled"},
    "sent": {"cancelled"},
    "rework_requested": {"sent", "cancelled"},
    "paid": set(),
    "cancelled": set(),
}


async def create_invoice(
    db: AsyncSession, tenant_id: uuid.UUID, deal_id: uuid.UUID, data: InvoiceCreate
) -> Invoice:
    invoice = Invoice(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        deal_id=deal_id,
        invoice_number=data.invoice_number,
        amount=data.amount,
        due_date=data.due_date,
    )
    db.add(invoice)
    await db.flush()
    await db.refresh(invoice)
    return invoice


async def list_invoices_for_deal(
    db: AsyncSession, tenant_id: uuid.UUID, deal_id: uuid.UUID
) -> list[Invoice]:
    result = await db.execute(
        select(Invoice)
        .where(Invoice.tenant_id == tenant_id, Invoice.deal_id == deal_id)
        .order_by(Invoice.created_at.desc())
    )
    return list(result.scalars().all())


async def get_invoice(
    db: AsyncSession, tenant_id: uuid.UUID, invoice_id: uuid.UUID
) -> Invoice | None:
    result = await db.execute(
        select(Invoice).where(Invoice.tenant_id == tenant_id, Invoice.id == invoice_id)
    )
    return result.scalar_one_or_none()


async def get_most_recent_open_invoice_for_deal(
    db: AsyncSession, tenant_id: uuid.UUID, deal_id: uuid.UUID
) -> Invoice | None:
    """"Open" = not cancelled — used by the rework-stage hook to find
    which invoice to flip. A deal with no invoice yet (or only a
    cancelled one) has nothing to flip, which is a no-op, not an error."""
    result = await db.execute(
        select(Invoice)
        .where(
            Invoice.tenant_id == tenant_id,
            Invoice.deal_id == deal_id,
            Invoice.status != "cancelled",
        )
        .order_by(Invoice.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def update_invoice(db: AsyncSession, invoice: Invoice, data: InvoiceUpdate) -> Invoice:
    updates = data.model_dump(exclude_unset=True)
    status = updates.pop("status", None)
    for key, value in updates.items():
        setattr(invoice, key, value)

    if status is not None:
        if status not in _CLIENT_ALLOWED_TRANSITIONS.get(invoice.status, set()):
            raise ApiError(
                400, VALIDATION_ERROR, f"Cannot transition from {invoice.status} to {status}"
            )
        invoice.status = status
        if status == "sent" and invoice.issued_at is None:
            invoice.issued_at = datetime.now(UTC)

    await db.flush()
    await db.refresh(invoice)
    return invoice


async def mark_rework_requested(db: AsyncSession, invoice: Invoice) -> Invoice:
    """System-only — app/api/deals.py's rework-stage hook. No transition
    validation: any non-terminal invoice can be sent back for rework
    regardless of its exact current status, since a human explicitly
    moved the deal into that stage."""
    if invoice.status in ("paid", "cancelled"):
        return invoice  # terminal — nothing to flip
    invoice.status = "rework_requested"
    invoice.was_reworked = True
    await db.flush()
    await db.refresh(invoice)
    return invoice


async def mark_paid(db: AsyncSession, invoice: Invoice) -> Invoice:
    """System-only — app/services/payment_service.py's paid-threshold
    check, once payments sum to >= the invoice amount."""
    invoice.status = "paid"
    await db.flush()
    await db.refresh(invoice)
    return invoice
