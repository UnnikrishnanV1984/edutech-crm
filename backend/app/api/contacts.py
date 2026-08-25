import uuid

from fastapi import APIRouter, Depends, Query, Request

from app.core.envelope import collection_envelope, data_envelope
from app.core.errors import NOT_FOUND, ApiError
from app.core.reassignment import guard_reassignment
from app.deps.scope import RowScope, get_row_scope
from app.deps.tenant import TenantContext, get_tenant_context
from app.schemas.activity import ActivityOut
from app.schemas.contact import ContactCreate, ContactOut, ContactUpdate
from app.services.activity_service import list_activities_for_contact
from app.services.contact_service import (
    create_contact,
    get_contact,
    list_contacts,
    update_contact,
)

router = APIRouter(prefix="/api/v1/contacts", tags=["contacts"])


@router.post("")
async def post_contact(
    request: Request,
    body: ContactCreate,
    context: TenantContext = Depends(get_tenant_context),
) -> dict:
    contact = await create_contact(
        context.db, context.tenant.id, body, default_owner_id=context.user.id
    )
    return data_envelope(
        ContactOut.model_validate(contact).model_dump(mode="json"), request.state.request_id
    )


@router.get("")
async def get_contacts(
    request: Request,
    search: str | None = None,
    lead_source: str | None = None,
    owner_id: uuid.UUID | None = None,
    stage_id: uuid.UUID | None = None,
    has_follow_up_flag: bool | None = None,
    sort: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    context: TenantContext = Depends(get_tenant_context),
    scope: RowScope = Depends(get_row_scope),
) -> dict:
    rows, total = await list_contacts(
        context.db,
        context.tenant.id,
        search=search,
        lead_source=lead_source,
        owner_id=owner_id,
        page=page,
        page_size=page_size,
        sort=sort,
        scoped_owner_ids=scope.owner_ids,
        stage_id=stage_id,
        has_follow_up_flag=has_follow_up_flag,
    )
    items = [
        ContactOut.model_validate(row["contact"])
        .model_copy(
            update={
                "stage_id": row["stage_id"],
                "stage_name": row["stage_name"],
                "sla_state": row["sla_state"],
                "has_open_follow_up": row["has_open_follow_up"],
            }
        )
        .model_dump(mode="json")
        for row in rows
    ]
    return collection_envelope(items, request.state.request_id, page, page_size, total)


@router.get("/{contact_id}")
async def get_contact_by_id(
    request: Request,
    contact_id: uuid.UUID,
    context: TenantContext = Depends(get_tenant_context),
    scope: RowScope = Depends(get_row_scope),
) -> dict:
    contact = await get_contact(context.db, context.tenant.id, contact_id, scope.owner_ids)
    if contact is None:
        raise ApiError(404, NOT_FOUND, "Contact not found")
    return data_envelope(
        ContactOut.model_validate(contact).model_dump(mode="json"), request.state.request_id
    )


@router.patch("/{contact_id}")
async def patch_contact(
    request: Request,
    contact_id: uuid.UUID,
    body: ContactUpdate,
    context: TenantContext = Depends(get_tenant_context),
    scope: RowScope = Depends(get_row_scope),
) -> dict:
    contact = await get_contact(context.db, context.tenant.id, contact_id, scope.owner_ids)
    if contact is None:
        raise ApiError(404, NOT_FOUND, "Contact not found")
    guard_reassignment(context, scope, body.model_dump(exclude_unset=True), "owner_id")
    contact = await update_contact(context.db, contact, body)
    return data_envelope(
        ContactOut.model_validate(contact).model_dump(mode="json"), request.state.request_id
    )


@router.get("/{contact_id}/activities")
async def get_contact_activities(
    request: Request,
    contact_id: uuid.UUID,
    context: TenantContext = Depends(get_tenant_context),
    scope: RowScope = Depends(get_row_scope),
) -> dict:
    contact = await get_contact(context.db, context.tenant.id, contact_id, scope.owner_ids)
    if contact is None:
        raise ApiError(404, NOT_FOUND, "Contact not found")
    activities = await list_activities_for_contact(context.db, context.tenant.id, contact_id)
    items = [ActivityOut.model_validate(a).model_dump(mode="json") for a in activities]
    return data_envelope(items, request.state.request_id)
