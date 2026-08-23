from fastapi import APIRouter, Depends, Request

from app.core.envelope import data_envelope
from app.deps.tenant import TenantContext, get_tenant_context
from app.schemas.user import MeData, TenantOut, UserOut

router = APIRouter(prefix="/api/v1", tags=["me"])


@router.get("/me")
async def get_me(
    request: Request,
    context: TenantContext = Depends(get_tenant_context),
) -> dict:
    data = MeData(
        user=UserOut.model_validate(context.user),
        tenant=TenantOut.model_validate(context.tenant),
    )
    return data_envelope(data.model_dump(mode="json"), request.state.request_id)
