import uuid

from fastapi import APIRouter, Depends, Request

from app.core.envelope import data_envelope
from app.core.errors import NOT_FOUND, ApiError
from app.deps.scope import RowScope, get_row_scope
from app.deps.tenant import TenantContext, get_tenant_context
from app.schemas.payment import PaymentCreate, PaymentOut
from app.services.deal_service import get_deal
from app.services.invoice_service import get_invoice
from app.services.payment_service import create_payment, list_payments_for_invoice

router = APIRouter(tags=["payments"])


def _out(payment) -> dict:
    return PaymentOut.model_validate(payment).model_dump(mode="json")


async def _get_invoice_in_scope(context: TenantContext, scope: RowScope, invoice_id: uuid.UUID):
    invoice = await get_invoice(context.db, context.tenant.id, invoice_id)
    if invoice is None:
        raise ApiError(404, NOT_FOUND, "Invoice not found")
    deal = await get_deal(context.db, context.tenant.id, invoice.deal_id, scope.owner_ids)
    if deal is None:
        raise ApiError(404, NOT_FOUND, "Invoice not found")
    return invoice


@router.post("/api/v1/invoices/{invoice_id}/payments")
async def post_payment(
    request: Request,
    invoice_id: uuid.UUID,
    body: PaymentCreate,
    context: TenantContext = Depends(get_tenant_context),
    scope: RowScope = Depends(get_row_scope),
) -> dict:
    invoice = await _get_invoice_in_scope(context, scope, invoice_id)
    payment = await create_payment(context.db, context.tenant.id, invoice, body)
    return data_envelope(_out(payment), request.state.request_id)


@router.get("/api/v1/invoices/{invoice_id}/payments")
async def get_payments(
    request: Request,
    invoice_id: uuid.UUID,
    context: TenantContext = Depends(get_tenant_context),
    scope: RowScope = Depends(get_row_scope),
) -> dict:
    await _get_invoice_in_scope(context, scope, invoice_id)
    payments = await list_payments_for_invoice(context.db, context.tenant.id, invoice_id)
    return data_envelope([_out(p) for p in payments], request.state.request_id)
