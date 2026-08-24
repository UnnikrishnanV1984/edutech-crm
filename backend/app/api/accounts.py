from fastapi import APIRouter, Depends, Request

from app.core.envelope import data_envelope
from app.deps.tenant import TenantContext, get_tenant_context
from app.schemas.account import AccountCreate, AccountOut
from app.services.account_service import create_account, list_accounts

router = APIRouter(prefix="/api/v1/accounts", tags=["accounts"])


@router.post("")
async def post_account(
    request: Request,
    body: AccountCreate,
    context: TenantContext = Depends(get_tenant_context),
) -> dict:
    account = await create_account(
        context.db, context.tenant.id, body, default_owner_id=context.user.id
    )
    return data_envelope(
        AccountOut.model_validate(account).model_dump(mode="json"), request.state.request_id
    )


@router.get("")
async def get_accounts(
    request: Request,
    context: TenantContext = Depends(get_tenant_context),
) -> dict:
    accounts = await list_accounts(context.db, context.tenant.id)
    items = [AccountOut.model_validate(a).model_dump(mode="json") for a in accounts]
    return data_envelope(items, request.state.request_id)
