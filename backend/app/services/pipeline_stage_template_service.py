from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pipeline_stage_template import PipelineStageTemplate

# No create/update/delete here — read-only, ever. See the model's own
# docstring and app/api/pipeline_stage_templates.py.


async def list_templates(db: AsyncSession) -> list[PipelineStageTemplate]:
    result = await db.execute(
        select(PipelineStageTemplate).order_by(
            PipelineStageTemplate.category, PipelineStageTemplate.default_sort_order
        )
    )
    return list(result.scalars().all())
