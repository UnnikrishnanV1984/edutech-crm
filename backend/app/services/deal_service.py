import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deal import Deal
from app.models.sla_state import SlaState
from app.schemas.deal import DealCreate, DealUpdate
from app.services.pipeline_stage_service import get_default_stage_id


async def create_deal(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    contact_id: uuid.UUID,
    data: DealCreate,
    default_owner_id: uuid.UUID,
) -> Deal:
    stage_id = data.stage_id or await get_default_stage_id(db, tenant_id)
    deal = Deal(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        contact_id=contact_id,
        course_id=data.course_id,
        stage_id=stage_id,
        owner_id=data.owner_id or default_owner_id,
        account_id=data.account_id,
        value=data.value,
        currency=data.currency,
    )
    db.add(deal)
    await db.flush()
    await db.refresh(deal)
    return deal


async def get_deal(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    deal_id: uuid.UUID,
    owner_ids: list[uuid.UUID] | None = None,
) -> Deal | None:
    """owner_ids is the RowScope filter (PHASE_3_PLAN.md §4) — None is
    unrestricted, for call sites checking existence rather than scoping
    a view/edit."""
    stmt = select(Deal).where(Deal.tenant_id == tenant_id, Deal.id == deal_id)
    if owner_ids is not None:
        stmt = stmt.where(Deal.owner_id.in_(owner_ids))
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_deals(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    stage_id: uuid.UUID | None,
    owner_id: uuid.UUID | None,
    contact_id: uuid.UUID | None,
    page: int,
    page_size: int,
    scoped_owner_ids: list[uuid.UUID] | None = None,
    course_id: uuid.UUID | None = None,
    sla_state: str | None = None,
) -> tuple[list[dict], int]:
    """Each deal is enriched with its current sla_state (outerjoin —
    None when no SLA policy has ticked it yet), needed for the Pipeline
    board's SLA-at-risk card marker and the SLA-state filter
    (design_handoff_crm_wireframes/README.md screen 2). One sla_states
    row per deal (the live rolling state, not a history log — same
    assumption report_service.py's get_my_queue already makes), so the
    join stays 1:1 and never multiplies the deal row count."""
    joined = (
        select(Deal, SlaState.state)
        .where(Deal.tenant_id == tenant_id)
        .outerjoin(SlaState, (SlaState.deal_id == Deal.id) & (SlaState.tenant_id == tenant_id))
    )
    if scoped_owner_ids is not None:
        joined = joined.where(Deal.owner_id.in_(scoped_owner_ids))
    if stage_id:
        joined = joined.where(Deal.stage_id == stage_id)
    if owner_id:
        joined = joined.where(Deal.owner_id == owner_id)
    if contact_id:
        joined = joined.where(Deal.contact_id == contact_id)
    if course_id:
        joined = joined.where(Deal.course_id == course_id)
    if sla_state:
        joined = joined.where(SlaState.state == sla_state)

    count_result = await db.execute(select(func.count()).select_from(joined.subquery()))
    total = count_result.scalar_one()

    joined = joined.order_by(Deal.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(joined)).all()
    return [{"deal": deal, "sla_state": state} for deal, state in rows], total


async def update_deal(
    db: AsyncSession, deal: Deal, data: DealUpdate
) -> tuple[Deal, uuid.UUID | None]:
    """Returns (deal, old_stage_id) — old_stage_id is set only when the
    stage actually changed, so the caller (deals API route, once
    activities exists — PHASE_1_PLAN.md §7 step 9) can log the
    transition without re-deriving it."""
    updates = data.model_dump(exclude_unset=True)
    old_stage_id: uuid.UUID | None = None
    if "stage_id" in updates and updates["stage_id"] != deal.stage_id:
        old_stage_id = deal.stage_id
        deal.stage_changed_at = datetime.now(UTC)

    for key, value in updates.items():
        setattr(deal, key, value)

    await db.flush()
    await db.refresh(deal)
    return deal, old_stage_id
