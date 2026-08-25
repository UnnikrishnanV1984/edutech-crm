"""Configurations "Branding" tab — logo/header image upload, applied
immediately (no draft/publish workflow, no versioning — a deliberately
smaller scope than the wireframe's full white-label system, product
decision 2026-08-25). Reuses the same S3/MinIO bucket and presign
primitives document_service.py already established, not a second
storage mechanism, but a longer-lived download URL: a document's
presigned GET URL (60s) is for one-off downloads, while a branding
image is embedded as a persistent <img src> across every page load, so
it needs a URL that survives a normal session rather than expiring
almost immediately.
"""

import re
import uuid

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.s3 import get_s3_client
from app.models.tenant_branding import TenantBranding

_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]")
UPLOAD_URL_TTL_SECONDS = 300
BRANDING_ASSET_URL_TTL_SECONDS = 3600


def _safe_filename(filename: str) -> str:
    base = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    return _UNSAFE_CHARS.sub("_", base) or "file"


def compute_branding_s3_key(tenant_id: uuid.UUID, asset_type: str, filename: str) -> str:
    """Always prefixed with tenant_id/branding/asset_type — same
    tamper-resistance reasoning as document_service.compute_s3_key: the
    confirm step rejects any s3_key not matching this exact prefix."""
    return f"{tenant_id}/branding/{asset_type}/{uuid.uuid4()}-{_safe_filename(filename)}"


def generate_branding_upload_url(s3_key: str, content_type: str) -> str:
    settings = get_settings()
    return get_s3_client().generate_presigned_url(
        "put_object",
        Params={"Bucket": settings.s3_bucket, "Key": s3_key, "ContentType": content_type},
        ExpiresIn=UPLOAD_URL_TTL_SECONDS,
    )


def generate_branding_asset_url(s3_key: str) -> str:
    settings = get_settings()
    return get_s3_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": s3_key},
        ExpiresIn=BRANDING_ASSET_URL_TTL_SECONDS,
    )


class InvalidS3Key(Exception):
    pass


async def get_branding(db: AsyncSession, tenant_id: uuid.UUID) -> TenantBranding | None:
    result = await db.execute(
        select(TenantBranding).where(TenantBranding.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()


async def set_branding_asset(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    asset_type: str,
    s3_key: str,
    updated_by: uuid.UUID,
) -> TenantBranding:
    expected_prefix = f"{tenant_id}/branding/{asset_type}/"
    if not s3_key.startswith(expected_prefix):
        raise InvalidS3Key(f"s3_key must start with {expected_prefix}")

    column = "logo_s3_key" if asset_type == "logo" else "header_image_s3_key"
    stmt = (
        pg_insert(TenantBranding)
        .values(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            updated_by=updated_by,
            updated_at=func.now(),
            **{column: s3_key},
        )
        .on_conflict_do_update(
            index_elements=[TenantBranding.tenant_id],
            set_={column: s3_key, "updated_by": updated_by, "updated_at": func.now()},
        )
    )
    await db.execute(stmt)
    await db.flush()
    return await get_branding(db, tenant_id)  # type: ignore[return-value]
