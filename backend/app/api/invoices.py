import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.exc import IntegrityError

from app.core.envelope import data_envelope
from app.core.errors import CONFLICT, NOT_FOUND, ApiError
from app.deps.scope import RowScope, get_row_scope
from app.deps.tenant import TenantContext, get_tenant_context
from app.schemas.invoice import InvoiceCreate, InvoiceOut, InvoiceUpdate
from app.services.deal_service import get_deal
from app.services.invoice_service import (
    create_invoice,
    get_invoice,
    list_invoices_for_deal,
    update_invoice,
)

router = APIRouter(tags=["invoices"])


def _out(invoice) -> dict:
    return InvoiceOut.model_validate(invoice).model_dump(mode="json")


async def _get_deal_in_scope(context: TenantContext, scope: RowScope, deal_id: uuid.UUID):
    deal = await get_deal(context.db, context.tenant.id, deal_id, scope.owner_ids)
    if deal is None:
        raise ApiError(404, NOT_FOUND, "Deal not found")
    return deal


@router.post("/api/v1/deals/{deal_id}/invoices")
async def post_invoice(
    request: Request,
    deal_id: uuid.UUID,
    body: InvoiceCreate,
    context: TenantContext = Depends(get_tenant_context),
    scope: RowScope = Depends(get_row_scope),
) -> dict:
    await _get_deal_in_scope(context, scope, deal_id)
    try:
        invoice = await create_invoice(context.db, context.tenant.id, deal_id, body)
    except IntegrityError as exc:
        await context.db.rollback()
        raise ApiError(409, CONFLICT, "An invoice with this number already exists") from exc
    return data_envelope(_out(invoice), request.state.request_id)


@router.get("/api/v1/deals/{deal_id}/invoices")
async def get_deal_invoices(
    request: Request,
    deal_id: uuid.UUID,
    context: TenantContext = Depends(get_tenant_context),
    scope: RowScope = Depends(get_row_scope),
) -> dict:
    await _get_deal_in_scope(context, scope, deal_id)
    invoices = await list_invoices_for_deal(context.db, context.tenant.id, deal_id)
    return data_envelope([_out(i) for i in invoices], request.state.request_id)


@router.get("/api/v1/invoices/{invoice_id}")
async def get_invoice_by_id(
    request: Request,
    invoice_id: uuid.UUID,
    context: TenantContext = Depends(get_tenant_context),
    scope: RowScope = Depends(get_row_scope),
) -> dict:
    invoice = await get_invoice(context.db, context.tenant.id, invoice_id)
    if invoice is None:
        raise ApiError(404, NOT_FOUND, "Invoice not found")
    await _get_deal_in_scope(context, scope, invoice.deal_id)
    return data_envelope(_out(invoice), request.state.request_id)


@router.patch("/api/v1/invoices/{invoice_id}")
async def patch_invoice(
    request: Request,
    invoice_id: uuid.UUID,
    body: InvoiceUpdate,
    context: TenantContext = Depends(get_tenant_context),
    scope: RowScope = Depends(get_row_scope),
) -> dict:
    invoice = await get_invoice(context.db, context.tenant.id, invoice_id)
    if invoice is None:
        raise ApiError(404, NOT_FOUND, "Invoice not found")
    await _get_deal_in_scope(context, scope, invoice.deal_id)
    invoice = await update_invoice(context.db, invoice, body)
    return data_envelope(_out(invoice), request.state.request_id)
