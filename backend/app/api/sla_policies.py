import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.exc import IntegrityError

from app.core.envelope import data_envelope
from app.core.errors import NOT_FOUND, VALIDATION_ERROR, ApiError
from app.deps.roles import require_admin
from app.deps.tenant import TenantContext
from app.schemas.sla_policy import SlaPolicyCreate, SlaPolicyOut, SlaPolicyUpdate
from app.services.sla_policy_service import (
    create_policy,
    get_policy,
    list_policies,
    update_policy,
)

router = APIRouter(prefix="/api/v1/sla-policies", tags=["sla-policies"])


def _out(policy) -> dict:
    return SlaPolicyOut.model_validate(policy).model_dump(mode="json")


@router.get("")
async def get_sla_policies(
    request: Request, context: TenantContext = Depends(require_admin)
) -> dict:
    policies = await list_policies(context.db, context.tenant.id)
    return data_envelope([_out(p) for p in policies], request.state.request_id)


@router.post("")
async def post_sla_policy(
    request: Request, body: SlaPolicyCreate, context: TenantContext = Depends(require_admin)
) -> dict:
    try:
        policy = await create_policy(context.db, context.tenant.id, body)
    except IntegrityError as exc:
        await context.db.rollback()
        raise ApiError(400, VALIDATION_ERROR, "stage_id does not exist") from exc
    return data_envelope(_out(policy), request.state.request_id)


@router.patch("/{policy_id}")
async def patch_sla_policy(
    request: Request,
    policy_id: uuid.UUID,
    body: SlaPolicyUpdate,
    context: TenantContext = Depends(require_admin),
) -> dict:
    policy = await get_policy(context.db, context.tenant.id, policy_id)
    if policy is None:
        raise ApiError(404, NOT_FOUND, "SLA policy not found")
    policy = await update_policy(context.db, policy, body)
    return data_envelope(_out(policy), request.state.request_id)
