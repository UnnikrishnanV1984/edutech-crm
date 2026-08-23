import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity


async def log_deal_stage_changed(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    contact_id: uuid.UUID,
    deal_id: uuid.UUID,
    actor_id: uuid.UUID,
    old_stage_id: uuid.UUID,
    new_stage_id: uuid.UUID,
) -> Activity:
    activity = Activity(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        contact_id=contact_id,
        deal_id=deal_id,
        type="deal_stage_changed",
        actor_id=actor_id,
        payload={"old_stage_id": str(old_stage_id), "new_stage_id": str(new_stage_id)},
    )
    db.add(activity)
    await db.flush()
    return activity


async def log_lead_captured(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    contact_id: uuid.UUID,
    deal_id: uuid.UUID | None,
    actor_id: uuid.UUID,
    source: str,
    external_id: str,
) -> Activity:
    """One per lead ingested by app/connectors/ or app/webhooks/ —
    actor_id is the round-robin-assigned owner of the resulting contact,
    standing in for "on behalf of" until a real system-actor concept
    exists (see the architect note in SEED_CONNECTORS_PLAN.md for why
    that wasn't added now). deal_id is None when the lead's course
    couldn't be resolved to a deal (PHASE_2_PLAN.md acceptance
    criterion 10) — the capture event is still logged."""
    activity = Activity(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        contact_id=contact_id,
        deal_id=deal_id,
        type="lead_captured",
        actor_id=actor_id,
        payload={"source": source, "external_id": external_id},
    )
    db.add(activity)
    await db.flush()
    return activity


async def list_activities_for_contact(
    db: AsyncSession, tenant_id: uuid.UUID, contact_id: uuid.UUID
) -> list[Activity]:
    result = await db.execute(
        select(Activity)
        .where(Activity.tenant_id == tenant_id, Activity.contact_id == contact_id)
        .order_by(Activity.created_at.desc())
    )
    return list(result.scalars().all())
