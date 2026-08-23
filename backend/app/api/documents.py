import uuid

from fastapi import APIRouter, Depends, Request

from app.core.envelope import data_envelope
from app.core.errors import NOT_FOUND, VALIDATION_ERROR, ApiError
from app.deps.tenant import TenantContext, get_tenant_context
from app.schemas.document import (
    DocumentCreate,
    DocumentOut,
    DownloadUrlResponse,
    UploadUrlRequest,
    UploadUrlResponse,
)
from app.services.contact_service import get_contact
from app.services.document_service import (
    InvalidS3Key,
    compute_s3_key,
    create_document,
    generate_download_url,
    generate_upload_url,
    get_document,
    list_documents_for_contact,
)

router = APIRouter(tags=["documents"])


@router.post("/api/v1/contacts/{contact_id}/documents/upload-url")
async def post_upload_url(
    request: Request,
    contact_id: uuid.UUID,
    body: UploadUrlRequest,
    context: TenantContext = Depends(get_tenant_context),
) -> dict:
    contact = await get_contact(context.db, context.tenant.id, contact_id)
    if contact is None:
        raise ApiError(404, NOT_FOUND, "Contact not found")

    s3_key = compute_s3_key(context.tenant.id, contact_id, body.filename)
    upload_url = generate_upload_url(s3_key, body.content_type)
    return data_envelope(
        UploadUrlResponse(upload_url=upload_url, s3_key=s3_key).model_dump(mode="json"),
        request.state.request_id,
    )


@router.post("/api/v1/contacts/{contact_id}/documents")
async def post_document(
    request: Request,
    contact_id: uuid.UUID,
    body: DocumentCreate,
    context: TenantContext = Depends(get_tenant_context),
) -> dict:
    contact = await get_contact(context.db, context.tenant.id, contact_id)
    if contact is None:
        raise ApiError(404, NOT_FOUND, "Contact not found")

    try:
        document = await create_document(
            context.db,
            context.tenant.id,
            contact_id,
            body.deal_id,
            body.filename,
            body.content_type,
            body.size_bytes,
            body.s3_key,
            uploaded_by=context.user.id,
        )
    except InvalidS3Key as exc:
        raise ApiError(400, VALIDATION_ERROR, "s3_key does not match this contact") from exc

    return data_envelope(
        DocumentOut.model_validate(document).model_dump(mode="json"), request.state.request_id
    )


@router.get("/api/v1/contacts/{contact_id}/documents")
async def get_documents(
    request: Request,
    contact_id: uuid.UUID,
    context: TenantContext = Depends(get_tenant_context),
) -> dict:
    contact = await get_contact(context.db, context.tenant.id, contact_id)
    if contact is None:
        raise ApiError(404, NOT_FOUND, "Contact not found")
    documents = await list_documents_for_contact(context.db, context.tenant.id, contact_id)
    items = [DocumentOut.model_validate(d).model_dump(mode="json") for d in documents]
    return data_envelope(items, request.state.request_id)


@router.get("/api/v1/documents/{document_id}/download-url")
async def get_download_url(
    request: Request,
    document_id: uuid.UUID,
    context: TenantContext = Depends(get_tenant_context),
) -> dict:
    document = await get_document(context.db, context.tenant.id, document_id)
    if document is None:
        raise ApiError(404, NOT_FOUND, "Document not found")
    download_url = generate_download_url(document.s3_key)
    return data_envelope(
        DownloadUrlResponse(download_url=download_url).model_dump(mode="json"),
        request.state.request_id,
    )
