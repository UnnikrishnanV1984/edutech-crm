import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import CONFLICT, VALIDATION_ERROR, ApiError
from app.models.deal import Deal
from app.models.pipeline_stage import PipelineStage
from app.models.pipeline_stage_default_snapshot import PipelineStageDefaultSnapshot
from app.models.sla_policy import SlaPolicy
from app.schemas.pipeline_stage import (
    PipelineStageBatchUpdate,
    PipelineStageCreate,
    PipelineStageUpdate,
)

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
        # Same transaction, same guard — this is the actual "snapshot
        # taken once, at provisioning" PIPELINE_CONFIG_RESET_PLAN.md §4.3
        # asks for; §4.2's migration-time backfill only exists to
        # backstop tenants provisioned before this table existed.
        db.add(
            PipelineStageDefaultSnapshot(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                name=name,
                sort_order=index,
                is_won=is_won,
                is_lost=is_lost,
            )
        )
    await db.flush()


async def get_default_snapshot(
    db: AsyncSession, tenant_id: uuid.UUID
) -> list[PipelineStageDefaultSnapshot]:
    result = await db.execute(
        select(PipelineStageDefaultSnapshot)
        .where(PipelineStageDefaultSnapshot.tenant_id == tenant_id)
        .order_by(PipelineStageDefaultSnapshot.sort_order)
    )
    return list(result.scalars().all())


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
        is_invoice_stage=data.is_invoice_stage,
        is_rework_stage=data.is_rework_stage,
    )
    db.add(stage)
    await db.flush()
    await db.refresh(stage)
    return stage


async def _in_use_reason(db: AsyncSession, tenant_id: uuid.UUID, stage_id: uuid.UUID) -> str | None:
    """Shared by delete_stage (single) and batch_update_stages/
    reset_to_default (whole-set) — same two checks, same order, so a
    stage blocked one way is blocked the other way for the same reason."""
    deal_count = await db.execute(
        select(func.count()).where(Deal.tenant_id == tenant_id, Deal.stage_id == stage_id)
    )
    if deal_count.scalar_one() > 0:
        return "in use by one or more deals"

    policy_count = await db.execute(
        select(func.count()).where(
            SlaPolicy.tenant_id == tenant_id, SlaPolicy.stage_id == stage_id
        )
    )
    if policy_count.scalar_one() > 0:
        return "in use by one or more SLA policies"

    return None


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
    reason = await _in_use_reason(db, tenant_id, stage.id)
    if reason is not None:
        raise ApiError(409, CONFLICT, f"Stage is {reason}")

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


async def batch_update_stages(
    db: AsyncSession, tenant_id: uuid.UUID, data: PipelineStageBatchUpdate
) -> list[PipelineStage]:
    """PIPELINE_CONFIG_RESET_PLAN.md §5.1 — full-replacement batch, all-
    or-nothing. Validates the whole proposed final state before writing
    anything: every id resolves to this tenant, the won/lost/open
    invariants delete_stage already enforces one-at-a-time still hold for
    the final set, and every stage that would be removed passes the same
    in-use check delete_stage does — collected across the whole set (not
    short-circuited on the first hit) so one response names every
    blocker, and a single blocker aborts the entire batch: nothing is
    written, not even an unrelated create/rename in the same payload.
    """
    existing = await db.execute(select(PipelineStage).where(PipelineStage.tenant_id == tenant_id))
    existing_by_id = {stage.id: stage for stage in existing.scalars().all()}

    kept_ids: set[uuid.UUID] = set()
    for entry in data.stages:
        if entry.id is not None:
            if entry.id not in existing_by_id:
                raise ApiError(
                    400, VALIDATION_ERROR, f"Stage {entry.id} does not belong to this tenant"
                )
            kept_ids.add(entry.id)
    removed_ids = set(existing_by_id) - kept_ids

    blockers: list[dict] = []
    for stage_id in removed_ids:
        reason = await _in_use_reason(db, tenant_id, stage_id)
        if reason is not None:
            stage = existing_by_id[stage_id]
            blockers.append({"stage_id": str(stage_id), "name": stage.name, "reason": reason})
    if blockers:
        raise ApiError(409, CONFLICT, "One or more stages can't be removed", details=blockers)

    # Won/lost/open invariant (same one delete_stage enforces one stage
    # at a time), evaluated against the *proposed final* set — kept
    # entries use their existing, immutable flags; new entries use the
    # payload's.
    final_is_won = [
        existing_by_id[e.id].is_won if e.id is not None else e.is_won for e in data.stages
    ]
    final_is_lost = [
        existing_by_id[e.id].is_lost if e.id is not None else e.is_lost for e in data.stages
    ]
    if not any(final_is_won):
        raise ApiError(400, VALIDATION_ERROR, "Final stage list must include a won stage")
    if not any(final_is_lost):
        raise ApiError(400, VALIDATION_ERROR, "Final stage list must include a lost stage")
    if not any(not w and not lost for w, lost in zip(final_is_won, final_is_lost, strict=True)):
        raise ApiError(400, VALIDATION_ERROR, "Final stage list must include an open stage")

    for stage_id in removed_ids:
        await db.delete(existing_by_id[stage_id])
    await db.flush()

    # Two-phase sort_order assignment, same trick reorder_stages already
    # uses (see its own docstring) — extended here to also cover
    # inserting brand-new rows in between the two phases, since a new
    # stage can be inserted directly at its final positive position the
    # moment every kept stage has been parked negative.
    for index, entry in enumerate(data.stages, start=1):
        if entry.id is not None:
            existing_by_id[entry.id].sort_order = -index
    await db.flush()

    for index, entry in enumerate(data.stages, start=1):
        if entry.id is None:
            db.add(
                PipelineStage(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    name=entry.name,
                    sort_order=index,
                    is_won=entry.is_won,
                    is_lost=entry.is_lost,
                    is_invoice_stage=entry.is_invoice_stage,
                    is_rework_stage=entry.is_rework_stage,
                )
            )
    await db.flush()

    for index, entry in enumerate(data.stages, start=1):
        if entry.id is not None:
            stage = existing_by_id[entry.id]
            stage.name = entry.name
            stage.sort_order = index
    await db.flush()

    result = await db.execute(
        select(PipelineStage)
        .where(PipelineStage.tenant_id == tenant_id)
        .order_by(PipelineStage.sort_order)
    )
    return list(result.scalars().all())


async def reset_to_default(db: AsyncSession, tenant_id: uuid.UUID) -> list[PipelineStage]:
    """PIPELINE_CONFIG_RESET_PLAN.md §5.2 — restores this tenant's
    pipeline_stages to exactly match its own pipeline_stage_default_snapshots
    (captured once, at provisioning — ensure_default_stages). Same in-use
    check as batch_update_stages, evaluated for *every* current stage
    (not just ones that differ from the snapshot) since every current
    stage gets replaced with a fresh row either way — any blocker aborts
    the whole reset, current configuration is left completely untouched.
    """
    snapshot = await get_default_snapshot(db, tenant_id)
    if not snapshot:
        # Shouldn't happen after migration 0027's backfill, but don't
        # silently wipe a tenant down to zero stages if it somehow did.
        raise ApiError(409, CONFLICT, "No default configuration is available for this tenant")

    existing = await db.execute(select(PipelineStage).where(PipelineStage.tenant_id == tenant_id))
    existing_stages = list(existing.scalars().all())

    blockers: list[dict] = []
    for stage in existing_stages:
        reason = await _in_use_reason(db, tenant_id, stage.id)
        if reason is not None:
            blockers.append({"stage_id": str(stage.id), "name": stage.name, "reason": reason})
    if blockers:
        raise ApiError(
            409, CONFLICT, "One or more current stages can't be reset", details=blockers
        )

    for stage in existing_stages:
        await db.delete(stage)
    await db.flush()

    for snap in snapshot:
        db.add(
            PipelineStage(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                name=snap.name,
                sort_order=snap.sort_order,
                is_won=snap.is_won,
                is_lost=snap.is_lost,
                is_invoice_stage=snap.is_invoice_stage,
                is_rework_stage=snap.is_rework_stage,
                win_probability_pct=snap.win_probability_pct,
            )
        )
    await db.flush()

    result = await db.execute(
        select(PipelineStage)
        .where(PipelineStage.tenant_id == tenant_id)
        .order_by(PipelineStage.sort_order)
    )
    return list(result.scalars().all())
