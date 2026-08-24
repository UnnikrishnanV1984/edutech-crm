"""GET-only, deliberately — see the model's own docstring and
PIPELINE_AND_REVENUE.md §2.6's architect review. No POST/PATCH/DELETE
route exists here, and none should ever be added: that's the entire
justification for this table having no tenant_id/RLS."""

from fastapi import APIRouter, Depends, Request

from app.core.envelope import data_envelope
from app.deps.roles import require_admin
from app.deps.tenant import TenantContext
from app.schemas.pipeline_stage_template import PipelineStageTemplateOut
from app.services.pipeline_stage_template_service import list_templates

router = APIRouter(prefix="/api/v1/pipeline-stage-templates", tags=["pipeline-stage-templates"])


@router.get("")
async def get_pipeline_stage_templates(
    request: Request,
    context: TenantContext = Depends(require_admin),
) -> dict:
    templates = await list_templates(context.db)
    items = [
        PipelineStageTemplateOut.model_validate(t).model_dump(mode="json") for t in templates
    ]
    return data_envelope(items, request.state.request_id)
