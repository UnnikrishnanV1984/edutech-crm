import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pipeline_stage import PipelineStage
from app.schemas.pipeline_stage import PipelineStageUpdate

# FEATURES_AND_PLAN.md's admission funnel. Seeded once per tenant, lazily
# — Phase 0 has no tenant-provisioning flow yet (DEVELOPMENT_PLAN.md §8),
# so there's no single moment to seed these at "tenant creation."
# is_won/is_lost, not the name, is what later phases read
# (PHASE_1_PLAN.md §4.2) — a tenant renaming "Enrolled" doesn't change
# what it means.
DEFAULT_STAGES = [
    ("Inquiry", False, False),
    ("Contacted", False, False),
    ("Demo scheduled", False, False),
    ("Demo attended", False, False),
    ("Application submitted", False, False),
    ("Fee paid", False, False),
    ("Enrolled", True, False),
    ("Dropped", False, True),
]


async def ensure_default_stages(db: AsyncSession, tenant_id: uuid.UUID) -> None:
    count_result = await db.execute(
        select(func.count()).select_from(
            select(PipelineStage).where(PipelineStage.tenant_id == tenant_id).subquery()
        )
    )
    if count_result.scalar_one() > 0:
        return
    for index, (name, is_won, is_lost) in enumerate(DEFAULT_STAGES, start=1):
        db.add(
            PipelineStage(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                name=name,
                sort_order=index,
                is_won=is_won,
                is_lost=is_lost,
            )
        )
    await db.flush()


async def list_stages(db: AsyncSession, tenant_id: uuid.UUID) -> list[PipelineStage]:
    await ensure_default_stages(db, tenant_id)
    result = await db.execute(
        select(PipelineStage)
        .where(PipelineStage.tenant_id == tenant_id)
        .order_by(PipelineStage.sort_order)
    )
    return list(result.scalars().all())


async def get_default_stage_id(db: AsyncSession, tenant_id: uuid.UUID) -> uuid.UUID:
    """First non-won/lost stage by sort_order — where a new deal starts
    (PHASE_1_PLAN.md §4.2)."""
    await ensure_default_stages(db, tenant_id)
    result = await db.execute(
        select(PipelineStage.id)
        .where(
            PipelineStage.tenant_id == tenant_id,
            PipelineStage.is_won.is_(False),
            PipelineStage.is_lost.is_(False),
        )
        .order_by(PipelineStage.sort_order)
        .limit(1)
    )
    stage_id = result.scalar_one_or_none()
    if stage_id is None:
        # Every tenant has at least one open stage in the default set;
        # this only fires if a tenant edited every stage into won/lost,
        # which the current PATCH (rename/reorder only) can't do — but
        # fail loudly rather than silently picking a won/lost stage.
        raise RuntimeError(f"Tenant {tenant_id} has no open pipeline stage")
    return stage_id


async def get_stage(
    db: AsyncSession, tenant_id: uuid.UUID, stage_id: uuid.UUID
) -> PipelineStage | None:
    result = await db.execute(
        select(PipelineStage).where(
            PipelineStage.tenant_id == tenant_id, PipelineStage.id == stage_id
        )
    )
    return result.scalar_one_or_none()


async def update_stage(
    db: AsyncSession, stage: PipelineStage, data: PipelineStageUpdate
) -> PipelineStage:
    updates = data.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(stage, key, value)
    await db.flush()
    await db.refresh(stage)
    return stage
