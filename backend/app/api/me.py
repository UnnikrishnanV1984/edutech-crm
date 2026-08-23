from fastapi import APIRouter, Depends, Request

from app.core.envelope import data_envelope
from app.deps.tenant import TenantContext, get_tenant_context
from app.schemas.user import MeData, TenantOut, UserOut
from app.services.user_service import upsert_user

router = APIRouter(prefix="/api/v1", tags=["me"])


@router.get("/me")
async def get_me(
    request: Request,
    context: TenantContext = Depends(get_tenant_context),
) -> dict:
    user = await upsert_user(
        db=context.db,
        tenant_id=context.tenant.id,
        keycloak_sub=context.user_id,
        email=context.user_email,
        full_name=context.user_full_name,
        role=context.user_role,
    )
    data = MeData(
        user=UserOut.model_validate(user),
        tenant=TenantOut.model_validate(context.tenant),
    )
    return data_envelope(data.model_dump(mode="json"), request.state.request_id)
