import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.exc import IntegrityError

from app.core.envelope import data_envelope
from app.core.errors import CONFLICT, NOT_FOUND, ApiError
from app.deps.roles import require_admin
from app.deps.tenant import TenantContext, get_tenant_context
from app.schemas.pipeline_stage import (
    PipelineStageCreate,
    PipelineStageOut,
    PipelineStageReorder,
    PipelineStageUpdate,
)
from app.services.pipeline_stage_service import (
    create_stage,
    delete_stage,
    get_stage,
    list_stages,
    reorder_stages,
    update_stage,
)

router = APIRouter(prefix="/api/v1/pipeline-stages", tags=["pipeline-stages"])


@router.get("")
async def get_pipeline_stages(
    request: Request,
    context: TenantContext = Depends(get_tenant_context),
) -> dict:
    stages = await list_stages(context.db, context.tenant.id)
    items = [PipelineStageOut.model_validate(s).model_dump(mode="json") for s in stages]
    return data_envelope(items, request.state.request_id)


@router.post("")
async def post_pipeline_stage(
    request: Request,
    body: PipelineStageCreate,
    context: TenantContext = Depends(require_admin),
) -> dict:
    try:
        stage = await create_stage(context.db, context.tenant.id, body)
    except IntegrityError as exc:
        await context.db.rollback()
        raise ApiError(409, CONFLICT, "A stage with that name already exists") from exc
    return data_envelope(
        PipelineStageOut.model_validate(stage).model_dump(mode="json"), request.state.request_id
    )


# Registered before "/{stage_id}" so FastAPI doesn't try to parse
# "reorder" as a UUID path param.
@router.patch("/reorder")
async def patch_pipeline_stages_reorder(
    request: Request,
    body: PipelineStageReorder,
    context: TenantContext = Depends(require_admin),
) -> dict:
    stages = await reorder_stages(context.db, context.tenant.id, body.stage_ids)
    items = [PipelineStageOut.model_validate(s).model_dump(mode="json") for s in stages]
    return data_envelope(items, request.state.request_id)


@router.patch("/{stage_id}")
async def patch_pipeline_stage(
    request: Request,
    stage_id: uuid.UUID,
    body: PipelineStageUpdate,
    context: TenantContext = Depends(require_admin),
) -> dict:
    stage = await get_stage(context.db, context.tenant.id, stage_id)
    if stage is None:
        raise ApiError(404, NOT_FOUND, "Pipeline stage not found")
    try:
        stage = await update_stage(context.db, stage, body)
    except IntegrityError as exc:
        await context.db.rollback()
        raise ApiError(
            409, CONFLICT, "Another stage already uses that name or sort order"
        ) from exc
    return data_envelope(
        PipelineStageOut.model_validate(stage).model_dump(mode="json"), request.state.request_id
    )


@router.delete("/{stage_id}")
async def delete_pipeline_stage(
    request: Request,
    stage_id: uuid.UUID,
    context: TenantContext = Depends(require_admin),
) -> dict:
    stage = await get_stage(context.db, context.tenant.id, stage_id)
    if stage is None:
        raise ApiError(404, NOT_FOUND, "Pipeline stage not found")
    await delete_stage(context.db, context.tenant.id, stage)
    return data_envelope({}, request.state.request_id)
