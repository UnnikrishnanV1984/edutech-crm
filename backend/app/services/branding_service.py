"""Configurations "Branding" tab — BRANDING_FULL_SYSTEM_PLAN.md,
architect-approved 2026-08-26. Draft/publish/version model: tenant_branding
is the mutable *draft* an admin edits; tenant_branding_versions is a
write-once snapshot history, and the highest version_number row for a
tenant is what's actually *live* — GET /api/v1/branding (the app-shell
read) is served from there, never from the draft. Asset uploads reuse
document_service.py's S3/MinIO presign primitives, not a second storage
mechanism, but a longer-lived download URL: a document's presigned GET
URL (60s) is for one-off downloads, while a branding image is embedded as
a persistent <img src> across every page load, so it needs a URL that
survives a normal session rather than expiring almost immediately.
"""

import re
import uuid

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.s3 import get_s3_client
from app.models.tenant_branding import (
    BRANDING_SNAPSHOT_FIELDS,
    TenantBranding,
    TenantBrandingVersion,
)
from app.models.user import User

_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]")
UPLOAD_URL_TTL_SECONDS = 300
BRANDING_ASSET_URL_TTL_SECONDS = 3600

_ASSET_COLUMN = {
    "logo": "logo_s3_key",
    "header": "header_image_s3_key",
    "favicon": "favicon_s3_key",
    "login_backdrop": "login_backdrop_s3_key",
}


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


# --- Draft ------------------------------------------------------------


async def get_draft(db: AsyncSession, tenant_id: uuid.UUID) -> TenantBranding | None:
    result = await db.execute(select(TenantBranding).where(TenantBranding.tenant_id == tenant_id))
    return result.scalar_one_or_none()


async def get_or_create_draft(db: AsyncSession, tenant_id: uuid.UUID) -> TenantBranding:
    draft = await get_draft(db, tenant_id)
    if draft is not None:
        return draft
    stmt = (
        pg_insert(TenantBranding)
        .values(id=uuid.uuid4(), tenant_id=tenant_id)
        .on_conflict_do_nothing(index_elements=[TenantBranding.tenant_id])
    )
    await db.execute(stmt)
    await db.flush()
    return await get_draft(db, tenant_id)  # type: ignore[return-value]


async def set_branding_asset(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    asset_type: str,
    s3_key: str,
    updated_by: uuid.UUID,
) -> TenantBranding:
    """Always writes to the draft — never live until Publish."""
    expected_prefix = f"{tenant_id}/branding/{asset_type}/"
    if not s3_key.startswith(expected_prefix):
        raise InvalidS3Key(f"s3_key must start with {expected_prefix}")

    column = _ASSET_COLUMN[asset_type]
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
    return await get_draft(db, tenant_id)  # type: ignore[return-value]


async def update_draft(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    updates: dict,
    updated_by: uuid.UUID,
) -> TenantBranding:
    """updates is the request's model_dump(exclude_unset=True) — only
    fields actually sent are touched, same convention decide_rule/
    workflow rules already use for a partial-update endpoint."""
    if not updates:
        return await get_or_create_draft(db, tenant_id)

    stmt = (
        pg_insert(TenantBranding)
        .values(id=uuid.uuid4(), tenant_id=tenant_id, updated_by=updated_by, **updates)
        .on_conflict_do_update(
            index_elements=[TenantBranding.tenant_id],
            set_={**updates, "updated_by": updated_by, "updated_at": func.now()},
        )
    )
    await db.execute(stmt)
    await db.flush()
    return await get_draft(db, tenant_id)  # type: ignore[return-value]


# --- Published (live) ---------------------------------------------------


async def get_latest_version(
    db: AsyncSession, tenant_id: uuid.UUID
) -> TenantBrandingVersion | None:
    result = await db.execute(
        select(TenantBrandingVersion)
        .where(TenantBrandingVersion.tenant_id == tenant_id)
        .order_by(TenantBrandingVersion.version_number.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def publish(
    db: AsyncSession, tenant_id: uuid.UUID, published_by: uuid.UUID
) -> TenantBrandingVersion:
    draft = await get_or_create_draft(db, tenant_id)
    latest = await get_latest_version(db, tenant_id)
    next_number = (latest.version_number + 1) if latest is not None else 1

    version = TenantBrandingVersion(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        version_number=next_number,
        published_by=published_by,
        **{field: getattr(draft, field) for field in BRANDING_SNAPSHOT_FIELDS},
    )
    db.add(version)
    await db.flush()
    await db.refresh(version)
    return version


async def discard_draft(
    db: AsyncSession, tenant_id: uuid.UUID, updated_by: uuid.UUID
) -> TenantBranding:
    """Resets the draft's editable fields to the latest published
    version's values, or to defaults if never published."""
    latest = await get_latest_version(db, tenant_id)
    reset_values = (
        {field: getattr(latest, field) for field in BRANDING_SNAPSHOT_FIELDS}
        if latest is not None
        else dict.fromkeys(BRANDING_SNAPSHOT_FIELDS)
        | {"header_background": "light", "typeface": "system"}
    )
    return await update_draft(db, tenant_id, reset_values, updated_by)


# --- Versions -------------------------------------------------------------


async def list_versions(db: AsyncSession, tenant_id: uuid.UUID) -> list[TenantBrandingVersion]:
    result = await db.execute(
        select(TenantBrandingVersion)
        .where(TenantBrandingVersion.tenant_id == tenant_id)
        .order_by(TenantBrandingVersion.version_number.desc())
    )
    return list(result.scalars().all())


async def get_version(
    db: AsyncSession, tenant_id: uuid.UUID, version_id: uuid.UUID
) -> TenantBrandingVersion | None:
    result = await db.execute(
        select(TenantBrandingVersion).where(
            TenantBrandingVersion.tenant_id == tenant_id, TenantBrandingVersion.id == version_id
        )
    )
    return result.scalar_one_or_none()


async def restore_version(
    db: AsyncSession, tenant_id: uuid.UUID, version: TenantBrandingVersion, updated_by: uuid.UUID
) -> TenantBranding:
    """Copies the version's fields into the draft. Does NOT publish — a
    second, explicit Publish is required to go live, matching the
    wireframe's distinct Restore-vs-Publish actions."""
    values = {field: getattr(version, field) for field in BRANDING_SNAPSHOT_FIELDS}
    return await update_draft(db, tenant_id, values, updated_by)


async def resolve_user_names(
    db: AsyncSession, tenant_id: uuid.UUID, user_ids: set[uuid.UUID]
) -> dict:
    if not user_ids:
        return {}
    result = await db.execute(
        select(User).where(User.tenant_id == tenant_id, User.id.in_(user_ids))
    )
    return {u.id: (u.full_name or u.email) for u in result.scalars().all()}
