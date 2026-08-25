import uuid

from fastapi import APIRouter, Depends, Request

from app.core.envelope import data_envelope
from app.core.errors import NOT_FOUND, VALIDATION_ERROR, ApiError
from app.deps.roles import require_admin
from app.deps.tenant import TenantContext, get_tenant_context
from app.schemas.branding import (
    BrandingConfirmRequest,
    BrandingDraftUpdate,
    BrandingUploadUrlRequest,
    BrandingUploadUrlResponse,
)
from app.services.branding_service import (
    InvalidS3Key,
    compute_branding_s3_key,
    discard_draft,
    generate_branding_asset_url,
    generate_branding_upload_url,
    get_latest_version,
    get_or_create_draft,
    get_version,
    list_versions,
    publish,
    resolve_user_names,
    restore_version,
    set_branding_asset,
    update_draft,
)

router = APIRouter(prefix="/api/v1/branding", tags=["branding"])


def _asset_url(s3_key: str | None) -> str | None:
    return generate_branding_asset_url(s3_key) if s3_key else None


def _live_out(version) -> dict:
    if version is None:
        return {
            "logo_url": None,
            "header_image_url": None,
            "favicon_url": None,
            "company_display_name": None,
            "accent_color": None,
            "header_background": "light",
            "typeface": "system",
            "updated_at": None,
        }
    return {
        "logo_url": _asset_url(version.logo_s3_key),
        "header_image_url": _asset_url(version.header_image_s3_key),
        "favicon_url": _asset_url(version.favicon_s3_key),
        "company_display_name": version.company_display_name,
        "accent_color": version.accent_color,
        "header_background": version.header_background,
        "typeface": version.typeface,
        "updated_at": version.published_at,
    }


def _draft_out(draft) -> dict:
    return {
        "logo_url": _asset_url(draft.logo_s3_key),
        "header_image_url": _asset_url(draft.header_image_s3_key),
        "favicon_url": _asset_url(draft.favicon_s3_key),
        "login_backdrop_url": _asset_url(draft.login_backdrop_s3_key),
        "company_display_name": draft.company_display_name,
        "accent_color": draft.accent_color,
        "header_background": draft.header_background,
        "typeface": draft.typeface,
        "custom_domain": draft.custom_domain,
        "updated_at": draft.updated_at,
    }


@router.get("")
async def get_branding_route(
    request: Request, context: TenantContext = Depends(get_tenant_context)
) -> dict:
    # Every authenticated role, not admin-only — the sidebar/app shell
    # renders this for everyone in the tenant. Served from the latest
    # *published version*, never the draft — nothing here reflects an
    # in-progress edit until Publish.
    version = await get_latest_version(context.db, context.tenant.id)
    return data_envelope(_live_out(version), request.state.request_id)


@router.get("/draft")
async def get_branding_draft_route(
    request: Request, context: TenantContext = Depends(require_admin)
) -> dict:
    draft = await get_or_create_draft(context.db, context.tenant.id)
    return data_envelope(_draft_out(draft), request.state.request_id)


@router.patch("/draft")
async def patch_branding_draft_route(
    request: Request,
    body: BrandingDraftUpdate,
    context: TenantContext = Depends(require_admin),
) -> dict:
    updates = body.model_dump(exclude_unset=True)
    draft = await update_draft(context.db, context.tenant.id, updates, context.user.id)
    return data_envelope(_draft_out(draft), request.state.request_id)


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
        draft = await set_branding_asset(
            context.db, context.tenant.id, body.asset_type, body.s3_key, context.user.id
        )
    except InvalidS3Key as exc:
        raise ApiError(400, VALIDATION_ERROR, "s3_key does not match this upload") from exc
    return data_envelope(_draft_out(draft), request.state.request_id)


@router.post("/publish")
async def post_branding_publish(
    request: Request, context: TenantContext = Depends(require_admin)
) -> dict:
    version = await publish(context.db, context.tenant.id, context.user.id)
    return data_envelope(_live_out(version), request.state.request_id)


@router.post("/discard")
async def post_branding_discard(
    request: Request, context: TenantContext = Depends(require_admin)
) -> dict:
    draft = await discard_draft(context.db, context.tenant.id, context.user.id)
    return data_envelope(_draft_out(draft), request.state.request_id)


@router.get("/versions")
async def get_branding_versions(
    request: Request, context: TenantContext = Depends(require_admin)
) -> dict:
    versions = await list_versions(context.db, context.tenant.id)
    names = await resolve_user_names(
        context.db, context.tenant.id, {v.published_by for v in versions}
    )
    latest_number = versions[0].version_number if versions else None
    items = [
        {
            "id": str(v.id),
            "version_number": v.version_number,
            "published_by_name": names.get(v.published_by),
            "published_at": v.published_at.isoformat(),
            "is_live": v.version_number == latest_number,
        }
        for v in versions
    ]
    return data_envelope(items, request.state.request_id)


@router.post("/versions/{version_id}/restore")
async def post_branding_version_restore(
    request: Request,
    version_id: uuid.UUID,
    context: TenantContext = Depends(require_admin),
) -> dict:
    version = await get_version(context.db, context.tenant.id, version_id)
    if version is None:
        raise ApiError(404, NOT_FOUND, "Branding version not found")
    draft = await restore_version(context.db, context.tenant.id, version, context.user.id)
    return data_envelope(_draft_out(draft), request.state.request_id)
