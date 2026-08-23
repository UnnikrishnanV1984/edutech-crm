import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.s3 import get_s3_client
from app.models.document import Document

_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]")
UPLOAD_URL_TTL_SECONDS = 300
DOWNLOAD_URL_TTL_SECONDS = 60


def _safe_filename(filename: str) -> str:
    # Strips any path component a client might sneak in and drops anything
    # that isn't a safe filename character — the key still isn't
    # client-controlled overall (see compute_s3_key), this only keeps the
    # human-readable suffix tidy.
    base = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    return _UNSAFE_CHARS.sub("_", base) or "file"


def compute_s3_key(tenant_id: uuid.UUID, contact_id: uuid.UUID, filename: str) -> str:
    """The only place an s3_key is ever generated. Always prefixed with
    tenant_id/contact_id — PHASE_1_PLAN.md §6: even a leaked presigned URL
    is scoped to one document, and the confirm step (create_document)
    rejects any s3_key not matching this exact prefix, so a tampered
    client-echoed key can never point outside the caller's own tenant."""
    return f"{tenant_id}/{contact_id}/{uuid.uuid4()}-{_safe_filename(filename)}"


def generate_upload_url(s3_key: str, content_type: str) -> str:
    settings = get_settings()
    return get_s3_client().generate_presigned_url(
        "put_object",
        Params={"Bucket": settings.s3_bucket, "Key": s3_key, "ContentType": content_type},
        ExpiresIn=UPLOAD_URL_TTL_SECONDS,
    )


def generate_download_url(s3_key: str) -> str:
    settings = get_settings()
    return get_s3_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": s3_key},
        ExpiresIn=DOWNLOAD_URL_TTL_SECONDS,
    )


class InvalidS3Key(Exception):
    pass


async def create_document(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    contact_id: uuid.UUID,
    deal_id: uuid.UUID | None,
    filename: str,
    content_type: str,
    size_bytes: int,
    s3_key: str,
    uploaded_by: uuid.UUID,
) -> Document:
    expected_prefix = f"{tenant_id}/{contact_id}/"
    if not s3_key.startswith(expected_prefix):
        raise InvalidS3Key(f"s3_key must start with {expected_prefix}")

    document = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        contact_id=contact_id,
        deal_id=deal_id,
        filename=filename,
        content_type=content_type,
        size_bytes=size_bytes,
        s3_key=s3_key,
        uploaded_by=uploaded_by,
    )
    db.add(document)
    await db.flush()
    await db.refresh(document)
    return document


async def get_document(
    db: AsyncSession, tenant_id: uuid.UUID, document_id: uuid.UUID
) -> Document | None:
    result = await db.execute(
        select(Document).where(Document.tenant_id == tenant_id, Document.id == document_id)
    )
    return result.scalar_one_or_none()


async def list_documents_for_contact(
    db: AsyncSession, tenant_id: uuid.UUID, contact_id: uuid.UUID
) -> list[Document]:
    result = await db.execute(
        select(Document)
        .where(Document.tenant_id == tenant_id, Document.contact_id == contact_id)
        .order_by(Document.created_at.desc())
    )
    return list(result.scalars().all())
