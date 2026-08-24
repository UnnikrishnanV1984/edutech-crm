import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import CONFLICT, VALIDATION_ERROR, ApiError
from app.models.deal import Deal
from app.models.pipeline_stage import PipelineStage
from app.models.sla_policy import SlaPolicy
from app.schemas.pipeline_stage import PipelineStageCreate, PipelineStageUpdate

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


async def create_stage(
    db: AsyncSession, tenant_id: uuid.UUID, data: PipelineStageCreate
) -> PipelineStage:
    """Always appended at the end (ADMIN_UX_IMPROVEMENTS_PLAN.md Sec4.2)
    — sort_order is not client-settable here, use reorder_stages after
    creating."""
    max_sort_order = await db.execute(
        select(func.max(PipelineStage.sort_order)).where(PipelineStage.tenant_id == tenant_id)
    )
    next_sort_order = (max_sort_order.scalar_one() or 0) + 1
    stage = PipelineStage(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name=data.name,
        sort_order=next_sort_order,
        is_won=data.is_won,
        is_lost=data.is_lost,
    )
    db.add(stage)
    await db.flush()
    await db.refresh(stage)
    return stage


async def delete_stage(db: AsyncSession, tenant_id: uuid.UUID, stage: PipelineStage) -> None:
    """409s instead of a raw FK violation when the stage is in use, and
    409s (an application-level check no DB constraint can express) when
    deleting it would leave the tenant without a stage a later phase
    depends on existing — ADMIN_UX_IMPROVEMENTS_PLAN.md Sec4.3.

    Known, documented gap: workflow_rules.actions/conditions/
    trigger_config is tenant-scoped JSONB that can reference a stage_id
    (e.g. a change_stage action's to_stage_id) with no FK to catch a
    dangling reference after delete — not checked here, flagged in the
    plan rather than solved (a rule referencing a deleted stage fails
    safely at evaluation time via _run_one_rule's existing retry-then-
    fail path, it doesn't corrupt data).
    """
    deal_count = await db.execute(
        select(func.count()).where(Deal.tenant_id == tenant_id, Deal.stage_id == stage.id)
    )
    if deal_count.scalar_one() > 0:
        raise ApiError(409, CONFLICT, "Stage is in use by one or more deals")

    policy_count = await db.execute(
        select(func.count()).where(
            SlaPolicy.tenant_id == tenant_id, SlaPolicy.stage_id == stage.id
        )
    )
    if policy_count.scalar_one() > 0:
        raise ApiError(409, CONFLICT, "Stage is in use by one or more SLA policies")

    if stage.is_won or stage.is_lost:
        flag = PipelineStage.is_won if stage.is_won else PipelineStage.is_lost
        remaining = await db.execute(
            select(func.count()).where(
                PipelineStage.tenant_id == tenant_id, flag.is_(True), PipelineStage.id != stage.id
            )
        )
        if remaining.scalar_one() == 0:
            kind = "won" if stage.is_won else "lost"
            raise ApiError(409, CONFLICT, f"Cannot delete the only {kind} stage")
    else:
        # Mirrors get_default_stage_id's existing invariant (line ~74
        # above) that every tenant has at least one open stage — that
        # invariant held automatically before delete existed; this is
        # the one place it can now be broken, so it's guarded here.
        remaining_open = await db.execute(
            select(func.count()).where(
                PipelineStage.tenant_id == tenant_id,
                PipelineStage.is_won.is_(False),
                PipelineStage.is_lost.is_(False),
                PipelineStage.id != stage.id,
            )
        )
        if remaining_open.scalar_one() == 0:
            raise ApiError(409, CONFLICT, "Cannot delete the only open stage")

    await db.delete(stage)
    await db.flush()


async def reorder_stages(
    db: AsyncSession, tenant_id: uuid.UUID, stage_ids: list[uuid.UUID]
) -> list[PipelineStage]:
    """Two-phase update within the existing (non-deferred)
    (tenant_id, sort_order) unique index, per
    ADMIN_UX_IMPROVEMENTS_PLAN.md Sec6.3 — deliberately not a
    DEFERRABLE-constraint change (that would be a schema change to a
    table already in production use, architect-gated). Phase one moves
    every listed stage to a unique negative placeholder (no tenant's
    real sort_order is ever negative, so this can't collide with an
    untouched sibling or with each other); phase two then writes final
    positive values in any order, safe because after phase one no row
    for this tenant holds a positive value yet.
    """
    existing = await db.execute(
        select(PipelineStage).where(PipelineStage.tenant_id == tenant_id)
    )
    stages_by_id = {stage.id: stage for stage in existing.scalars().all()}

    if len(stage_ids) != len(stages_by_id) or set(stage_ids) != set(stages_by_id.keys()):
        raise ApiError(
            400,
            VALIDATION_ERROR,
            "stage_ids must be exactly the tenant's current set of pipeline stages, no duplicates",
        )

    for index, stage_id in enumerate(stage_ids, start=1):
        stages_by_id[stage_id].sort_order = -index
    await db.flush()

    for index, stage_id in enumerate(stage_ids, start=1):
        stages_by_id[stage_id].sort_order = index
    await db.flush()

    result = await db.execute(
        select(PipelineStage)
        .where(PipelineStage.tenant_id == tenant_id)
        .order_by(PipelineStage.sort_order)
    )
    return list(result.scalars().all())
