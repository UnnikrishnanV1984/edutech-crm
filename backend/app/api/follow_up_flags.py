import uuid

from fastapi import APIRouter, Depends, Request

from app.core.envelope import data_envelope
from app.core.errors import FORBIDDEN, NOT_FOUND, ApiError
from app.deps.roles import require_manager_or_admin
from app.deps.tenant import TenantContext
from app.schemas.follow_up_flag import FollowUpFlagCreate, FollowUpFlagOut, FollowUpFlagUpdate
from app.services.follow_up_flag_service import (
    create_flag,
    enrich_flags,
    get_flag,
    list_flags,
    resolve_flag,
    snooze_flag,
)

router = APIRouter(prefix="/api/v1/follow-up-flags", tags=["follow-up-flags"])


def _out(flag, enrichment: dict | None = None) -> dict:
    data = {column.name: getattr(flag, column.name) for column in flag.__table__.columns}
    if enrichment:
        data.update(enrichment)
    return FollowUpFlagOut.model_validate(data).model_dump(mode="json")


@router.get("")
async def get_follow_up_flags(
    request: Request,
    contact_id: uuid.UUID | None = None,
    manager_id: uuid.UUID | None = None,
    context: TenantContext = Depends(require_manager_or_admin),
) -> dict:
    # manager_id is only ever honored for an Admin caller — REQUIREMENTS.md
    # §4.3 makes this strictly the manager's own personal tracking list, so
    # a non-admin caller can't broaden or redirect it to anyone else's,
    # same as GET /escalations' assigned_to scoping.
    scoped_manager_id = context.user.id if context.user_role != "admin" else manager_id
    flags = await list_flags(context.db, context.tenant.id, scoped_manager_id, contact_id)
    enrichment = await enrich_flags(context.db, context.tenant.id, flags)
    return data_envelope(
        [_out(f, enrichment.get(f.id)) for f in flags], request.state.request_id
    )


@router.post("")
async def post_follow_up_flag(
    request: Request,
    body: FollowUpFlagCreate,
    context: TenantContext = Depends(require_manager_or_admin),
) -> dict:
    flag = await create_flag(context.db, context.tenant.id, context.user.id, body)
    return data_envelope(_out(flag), request.state.request_id)


@router.patch("/{flag_id}")
async def patch_follow_up_flag(
    request: Request,
    flag_id: uuid.UUID,
    body: FollowUpFlagUpdate = FollowUpFlagUpdate(),
    context: TenantContext = Depends(require_manager_or_admin),
) -> dict:
    flag = await get_flag(context.db, context.tenant.id, flag_id)
    if flag is None:
        raise ApiError(404, NOT_FOUND, "Follow-up flag not found")
    if context.user_role != "admin" and flag.manager_id != context.user.id:
        raise ApiError(403, FORBIDDEN, "Not your follow-up flag")
    if body.remind_on is not None:
        flag = await snooze_flag(context.db, flag, body.remind_on)
    else:
        flag = await resolve_flag(context.db, flag)
    return data_envelope(_out(flag), request.state.request_id)
