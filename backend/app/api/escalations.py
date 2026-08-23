import uuid

from fastapi import APIRouter, Depends, Request

from app.core.envelope import data_envelope
from app.core.errors import FORBIDDEN, NOT_FOUND, ApiError
from app.deps.tenant import TenantContext, get_tenant_context
from app.schemas.escalation import EscalationCreate, EscalationOut, EscalationUpdate
from app.services.escalation_service import (
    get_escalation,
    list_escalations,
    raise_manual_escalation,
    update_escalation,
)

router = APIRouter(prefix="/api/v1/escalations", tags=["escalations"])


def _out(escalation) -> dict:
    return EscalationOut.model_validate(escalation).model_dump(mode="json")


@router.get("")
async def get_escalations(
    request: Request, context: TenantContext = Depends(get_tenant_context)
) -> dict:
    assigned_to = None if context.user_role == "admin" else context.user.id
    escalations = await list_escalations(context.db, context.tenant.id, assigned_to)
    return data_envelope([_out(e) for e in escalations], request.state.request_id)


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
        context.db, escalation, body.status, body.resolution_note, body.reassign_to
    )
    return data_envelope(_out(escalation), request.state.request_id)
