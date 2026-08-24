"""PIPELINE_AND_REVENUE_PLAN.md §5.5 — recording a payment recomputes its
parent invoice's paid total in the same transaction; once the sum
reaches the invoice's amount, this is the only path that can ever set
an invoice's status to 'paid' (app/schemas/invoice.py's InvoiceUpdate
rejects 'paid' as a client-supplied value)."""

import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invoice import Invoice
from app.models.payment import Payment
from app.schemas.payment import PaymentCreate
from app.services.invoice_service import mark_paid


async def create_payment(
    db: AsyncSession, tenant_id: uuid.UUID, invoice: Invoice, data: PaymentCreate
) -> Payment:
    """invoice must already be confirmed to belong to tenant_id by the
    caller (app/api/payments.py) — invoice_id has no FK to check this at
    the DB level (0024's own docstring explains why), so this is the one
    real enforcement point."""
    payment = Payment(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        invoice_id=invoice.id,
        amount=data.amount,
        method=data.method,
        **({"paid_at": data.paid_at} if data.paid_at is not None else {}),
    )
    db.add(payment)
    await db.flush()

    total_paid = await db.execute(
        select(func.coalesce(func.sum(Payment.amount), Decimal("0"))).where(
            Payment.tenant_id == tenant_id, Payment.invoice_id == invoice.id
        )
    )
    if total_paid.scalar_one() >= invoice.amount:
        await mark_paid(db, invoice)

    await db.refresh(payment)
    return payment


async def list_payments_for_invoice(
    db: AsyncSession, tenant_id: uuid.UUID, invoice_id: uuid.UUID
) -> list[Payment]:
    result = await db.execute(
        select(Payment)
        .where(Payment.tenant_id == tenant_id, Payment.invoice_id == invoice_id)
        .order_by(Payment.paid_at.desc())
    )
    return list(result.scalars().all())
