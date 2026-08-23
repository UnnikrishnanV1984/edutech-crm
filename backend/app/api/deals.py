import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.exc import IntegrityError

from app.core.envelope import collection_envelope, data_envelope
from app.core.errors import NOT_FOUND, VALIDATION_ERROR, ApiError
from app.core.reassignment import guard_reassignment
from app.deps.scope import RowScope, get_row_scope
from app.deps.tenant import TenantContext, get_tenant_context
from app.schemas.deal import DealCreate, DealOut, DealUpdate
from app.services.activity_service import log_deal_stage_changed
from app.services.contact_service import get_contact
from app.services.deal_service import create_deal, get_deal, list_deals, update_deal

router = APIRouter(tags=["deals"])


@router.post("/api/v1/contacts/{contact_id}/deals")
async def post_deal(
    request: Request,
    contact_id: uuid.UUID,
    body: DealCreate,
    context: TenantContext = Depends(get_tenant_context),
) -> dict:
    contact = await get_contact(context.db, context.tenant.id, contact_id)
    if contact is None:
        raise ApiError(404, NOT_FOUND, "Contact not found")

    try:
        deal = await create_deal(
            context.db, context.tenant.id, contact_id, body, default_owner_id=context.user.id
        )
    except IntegrityError as exc:
        await context.db.rollback()
        raise ApiError(
            400, VALIDATION_ERROR, "course_id, stage_id, or owner_id does not exist"
        ) from exc

    return data_envelope(
        DealOut.model_validate(deal).model_dump(mode="json"), request.state.request_id
    )


@router.get("/api/v1/deals")
async def get_deals(
    request: Request,
    stage_id: uuid.UUID | None = None,
    owner_id: uuid.UUID | None = None,
    contact_id: uuid.UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    context: TenantContext = Depends(get_tenant_context),
    scope: RowScope = Depends(get_row_scope),
) -> dict:
    deals, total = await list_deals(
        context.db,
        context.tenant.id,
        stage_id,
        owner_id,
        contact_id,
        page,
        page_size,
        scoped_owner_ids=scope.owner_ids,
    )
    items = [DealOut.model_validate(d).model_dump(mode="json") for d in deals]
    return collection_envelope(items, request.state.request_id, page, page_size, total)


@router.get("/api/v1/deals/{deal_id}")
async def get_deal_by_id(
    request: Request,
    deal_id: uuid.UUID,
    context: TenantContext = Depends(get_tenant_context),
    scope: RowScope = Depends(get_row_scope),
) -> dict:
    deal = await get_deal(context.db, context.tenant.id, deal_id, scope.owner_ids)
    if deal is None:
        raise ApiError(404, NOT_FOUND, "Deal not found")
    return data_envelope(
        DealOut.model_validate(deal).model_dump(mode="json"), request.state.request_id
    )


@router.patch("/api/v1/deals/{deal_id}")
async def patch_deal(
    request: Request,
    deal_id: uuid.UUID,
    body: DealUpdate,
    context: TenantContext = Depends(get_tenant_context),
    scope: RowScope = Depends(get_row_scope),
) -> dict:
    deal = await get_deal(context.db, context.tenant.id, deal_id, scope.owner_ids)
    if deal is None:
        raise ApiError(404, NOT_FOUND, "Deal not found")
    guard_reassignment(context, scope, body.model_dump(exclude_unset=True), "owner_id")

    try:
        deal, old_stage_id = await update_deal(context.db, deal, body)
    except IntegrityError as exc:
        await context.db.rollback()
        raise ApiError(
            400, VALIDATION_ERROR, "course_id, stage_id, or owner_id does not exist"
        ) from exc

    if old_stage_id is not None:
        await log_deal_stage_changed(
            context.db,
            context.tenant.id,
            deal.contact_id,
            deal.id,
            actor_id=context.user.id,
            old_stage_id=old_stage_id,
            new_stage_id=deal.stage_id,
        )

    return data_envelope(
        DealOut.model_validate(deal).model_dump(mode="json"), request.state.request_id
    )
