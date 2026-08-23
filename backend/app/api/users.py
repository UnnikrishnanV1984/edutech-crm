import uuid

from fastapi import APIRouter, Depends, Request

from app.core.envelope import data_envelope
from app.core.errors import NOT_FOUND, ApiError
from app.deps.roles import require_admin
from app.deps.tenant import TenantContext, get_tenant_context
from app.schemas.user import UserOut, UserUpdate
from app.services.user_list_service import list_users
from app.services.user_service import get_user, update_user_manager

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("")
async def get_users(
    request: Request,
    context: TenantContext = Depends(get_tenant_context),
) -> dict:
    users = await list_users(context.db, context.tenant.id)
    items = [UserOut.model_validate(u).model_dump(mode="json") for u in users]
    return data_envelope(items, request.state.request_id)


@router.patch("/{user_id}")
async def patch_user(
    request: Request,
    user_id: uuid.UUID,
    body: UserUpdate,
    context: TenantContext = Depends(require_admin),
) -> dict:
    user = await get_user(context.db, context.tenant.id, user_id)
    if user is None:
        raise ApiError(404, NOT_FOUND, "User not found")
    updates = body.model_dump(exclude_unset=True)
    if "manager_id" in updates:
        user = await update_user_manager(context.db, context.tenant.id, user, updates["manager_id"])
    return data_envelope(
        UserOut.model_validate(user).model_dump(mode="json"), request.state.request_id
    )
