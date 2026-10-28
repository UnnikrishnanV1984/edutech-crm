import uuid

from fastapi import APIRouter, Depends, Query, Request

from app.core.envelope import collection_envelope, data_envelope
from app.core.errors import FORBIDDEN, NOT_FOUND, VALIDATION_ERROR, ApiError
from app.deps.tenant import TenantContext, get_tenant_context
from app.schemas.escalation import EscalationCreate, EscalationOut, EscalationUpdate
from app.services.escalation_service import (
    enrich_escalations,
    get_escalation,
    list_escalations,
    raise_manual_escalation,
    update_escalation,
)

router = APIRouter(prefix="/api/v1/escalations", tags=["escalations"])

_VALID_STATUSES = {"open", "acknowledged", "resolved", "reassigned", "snoozed"}


def _out(escalation, enrichment: dict | None = None) -> dict:
    data = {
        column.name: getattr(escalation, column.name)
        for column in escalation.__table__.columns
    }
    if enrichment:
        data.update(enrichment)
    return EscalationOut.model_validate(data).model_dump(mode="json")


@router.get("")
async def get_escalations(
    request: Request,
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    context: TenantContext = Depends(get_tenant_context),
) -> dict:
    if status is not None and status not in _VALID_STATUSES:
        raise ApiError(400, VALIDATION_ERROR, f"Unknown status: {status}")
    assigned_to = None if context.user_role == "admin" else context.user.id
    escalations, total = await list_escalations(
        context.db, context.tenant.id, assigned_to, status, page, page_size
    )
    enrichment = await enrich_escalations(context.db, context.tenant.id, escalations)
    items = [_out(e, enrichment.get(e.id)) for e in escalations]
    return collection_envelope(items, request.state.request_id, page, page_size, total)


@router.post("")
async def post_escalation(
    request: Request,
    body: EscalationCreate,
    context: TenantContext = Depends(get_tenant_context),
) -> dict:
    escalation = await raise_manual_escalation(
        context.db, context.tenant.id, context.user.id, body
    )
    if escalation is None:
        raise ApiError(404, NOT_FOUND, "Deal or task not found")
    return data_envelope(_out(escalation), request.state.request_id)


@router.patch("/{escalation_id}")
async def patch_escalation(
    request: Request,
    escalation_id: uuid.UUID,
    body: EscalationUpdate,
    context: TenantContext = Depends(get_tenant_context),
) -> dict:
    escalation = await get_escalation(context.db, context.tenant.id, escalation_id)
    if escalation is None:
        raise ApiError(404, NOT_FOUND, "Escalation not found")
    if context.user_role != "admin" and escalation.assigned_to != context.user.id:
        raise ApiError(403, FORBIDDEN, "Only the assigned manager or an admin can act on this")
    escalation = await update_escalation(
        context.db,
        escalation,
        body.status,
        body.resolution_note,
        body.reassign_to,
        context.user.id,
        body.snoozed_until,
    )
    return data_envelope(_out(escalation), request.state.request_id)
