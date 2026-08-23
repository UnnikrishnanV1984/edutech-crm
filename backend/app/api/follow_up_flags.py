import uuid

from fastapi import APIRouter, Depends, Request

from app.core.envelope import data_envelope
from app.core.errors import FORBIDDEN, NOT_FOUND, ApiError
from app.deps.tenant import TenantContext, get_tenant_context
from app.schemas.follow_up_flag import FollowUpFlagCreate, FollowUpFlagOut
from app.services.follow_up_flag_service import create_flag, get_flag, list_flags, resolve_flag

router = APIRouter(prefix="/api/v1/follow-up-flags", tags=["follow-up-flags"])


def _out(flag) -> dict:
    return FollowUpFlagOut.model_validate(flag).model_dump(mode="json")


def _require_manager_or_admin(context: TenantContext) -> None:
    """The manager's own personal tracking tool (REQUIREMENTS.md §4.3) —
    Staff has no use for it and isn't granted access, unlike escalations
    which Staff can at least raise."""
    if context.user_role not in ("manager", "admin"):
        raise ApiError(403, FORBIDDEN, "Manager or admin role required")


@router.get("")
async def get_follow_up_flags(
    request: Request, context: TenantContext = Depends(get_tenant_context)
) -> dict:
    _require_manager_or_admin(context)
    manager_id = None if context.user_role == "admin" else context.user.id
    flags = await list_flags(context.db, context.tenant.id, manager_id)
    return data_envelope([_out(f) for f in flags], request.state.request_id)


@router.post("")
async def post_follow_up_flag(
    request: Request,
    body: FollowUpFlagCreate,
    context: TenantContext = Depends(get_tenant_context),
) -> dict:
    _require_manager_or_admin(context)
    flag = await create_flag(context.db, context.tenant.id, context.user.id, body)
    return data_envelope(_out(flag), request.state.request_id)


@router.patch("/{flag_id}")
async def patch_follow_up_flag(
    request: Request,
    flag_id: uuid.UUID,
    context: TenantContext = Depends(get_tenant_context),
) -> dict:
    _require_manager_or_admin(context)
    flag = await get_flag(context.db, context.tenant.id, flag_id)
    if flag is None:
        raise ApiError(404, NOT_FOUND, "Follow-up flag not found")
    if context.user_role != "admin" and flag.manager_id != context.user.id:
        raise ApiError(403, FORBIDDEN, "Not your follow-up flag")
    flag = await resolve_flag(context.db, flag)
    return data_envelope(_out(flag), request.state.request_id)
