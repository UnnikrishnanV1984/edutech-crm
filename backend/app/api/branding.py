from fastapi import APIRouter, Depends, Request

from app.core.envelope import data_envelope
from app.core.errors import VALIDATION_ERROR, ApiError
from app.deps.roles import require_admin
from app.deps.tenant import TenantContext, get_tenant_context
from app.schemas.branding import (
    BrandingConfirmRequest,
    BrandingOut,
    BrandingUploadUrlRequest,
    BrandingUploadUrlResponse,
)
from app.services.branding_service import (
    InvalidS3Key,
    compute_branding_s3_key,
    generate_branding_asset_url,
    generate_branding_upload_url,
    get_branding,
    set_branding_asset,
)

router = APIRouter(prefix="/api/v1/branding", tags=["branding"])


def _out(branding) -> dict:
    if branding is None:
        return BrandingOut(logo_url=None, header_image_url=None, updated_at=None).model_dump(
            mode="json"
        )
    return BrandingOut(
        logo_url=(
            generate_branding_asset_url(branding.logo_s3_key) if branding.logo_s3_key else None
        ),
        header_image_url=(
            generate_branding_asset_url(branding.header_image_s3_key)
            if branding.header_image_s3_key
            else None
        ),
        updated_at=branding.updated_at,
    ).model_dump(mode="json")


@router.get("")
async def get_branding_route(
    request: Request, context: TenantContext = Depends(get_tenant_context)
) -> dict:
    # Every authenticated role, not admin-only — the sidebar renders the
    # logo for everyone in the tenant, same as every other page shell
    # element.
    branding = await get_branding(context.db, context.tenant.id)
    return data_envelope(_out(branding), request.state.request_id)


@router.post("/upload-url")
async def post_branding_upload_url(
    request: Request,
    body: BrandingUploadUrlRequest,
    context: TenantContext = Depends(require_admin),
) -> dict:
    if not body.content_type.startswith("image/"):
        raise ApiError(400, VALIDATION_ERROR, "Only image uploads are accepted")
    s3_key = compute_branding_s3_key(context.tenant.id, body.asset_type, body.filename)
    upload_url = generate_branding_upload_url(s3_key, body.content_type)
    return data_envelope(
        BrandingUploadUrlResponse(upload_url=upload_url, s3_key=s3_key).model_dump(mode="json"),
        request.state.request_id,
    )


@router.post("/confirm")
async def post_branding_confirm(
    request: Request,
    body: BrandingConfirmRequest,
    context: TenantContext = Depends(require_admin),
) -> dict:
    try:
        branding = await set_branding_asset(
            context.db, context.tenant.id, body.asset_type, body.s3_key, context.user.id
        )
    except InvalidS3Key as exc:
        raise ApiError(400, VALIDATION_ERROR, "s3_key does not match this upload") from exc
    return data_envelope(_out(branding), request.state.request_id)
