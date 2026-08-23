import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sla_policy import SlaPolicy
from app.schemas.sla_policy import SlaPolicyCreate, SlaPolicyUpdate


async def create_policy(
    db: AsyncSession, tenant_id: uuid.UUID, data: SlaPolicyCreate
) -> SlaPolicy:
    policy = SlaPolicy(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name=data.name,
        applies_to=data.applies_to,
        stage_id=data.stage_id,
        task_type=data.task_type,
        target_minutes=data.target_minutes,
        warning_threshold_pct=data.warning_threshold_pct,
    )
    db.add(policy)
    await db.flush()
    await db.refresh(policy)
    return policy


async def list_policies(db: AsyncSession, tenant_id: uuid.UUID) -> list[SlaPolicy]:
    result = await db.execute(
        select(SlaPolicy).where(SlaPolicy.tenant_id == tenant_id).order_by(SlaPolicy.created_at)
    )
    return list(result.scalars().all())


async def get_policy(
    db: AsyncSession, tenant_id: uuid.UUID, policy_id: uuid.UUID
) -> SlaPolicy | None:
    result = await db.execute(
        select(SlaPolicy).where(SlaPolicy.tenant_id == tenant_id, SlaPolicy.id == policy_id)
    )
    return result.scalar_one_or_none()


async def update_policy(db: AsyncSession, policy: SlaPolicy, data: SlaPolicyUpdate) -> SlaPolicy:
    updates = data.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(policy, key, value)
    await db.flush()
    await db.refresh(policy)
    return policy


async def list_active_policies(db: AsyncSession, tenant_id: uuid.UUID) -> list[SlaPolicy]:
    """Used by app/workers/sla.py's compute_sla_states — only active
    policies are ticked."""
    result = await db.execute(
        select(SlaPolicy).where(SlaPolicy.tenant_id == tenant_id, SlaPolicy.status == "active")
    )
    return list(result.scalars().all())
