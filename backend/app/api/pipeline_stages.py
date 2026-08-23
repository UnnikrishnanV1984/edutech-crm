import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.exc import IntegrityError

from app.core.envelope import data_envelope
from app.core.errors import CONFLICT, NOT_FOUND, ApiError
from app.deps.tenant import TenantContext, get_tenant_context
from app.schemas.pipeline_stage import PipelineStageOut, PipelineStageUpdate
from app.services.pipeline_stage_service import get_stage, list_stages, update_stage

router = APIRouter(prefix="/api/v1/pipeline-stages", tags=["pipeline-stages"])


@router.get("")
async def get_pipeline_stages(
    request: Request,
    context: TenantContext = Depends(get_tenant_context),
) -> dict:
    stages = await list_stages(context.db, context.tenant.id)
    items = [PipelineStageOut.model_validate(s).model_dump(mode="json") for s in stages]
    return data_envelope(items, request.state.request_id)


@router.patch("/{stage_id}")
async def patch_pipeline_stage(
    request: Request,
    stage_id: uuid.UUID,
    body: PipelineStageUpdate,
    context: TenantContext = Depends(get_tenant_context),
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
