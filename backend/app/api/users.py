from fastapi import APIRouter, Depends, Request

from app.core.envelope import data_envelope
from app.deps.tenant import TenantContext, get_tenant_context
from app.schemas.user import UserOut
from app.services.user_list_service import list_users

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("")
async def get_users(
    request: Request,
    context: TenantContext = Depends(get_tenant_context),
) -> dict:
    users = await list_users(context.db, context.tenant.id)
    items = [UserOut.model_validate(u).model_dump(mode="json") for u in users]
    return data_envelope(items, request.state.request_id)
