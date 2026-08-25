import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.follow_up_flag import FollowUpFlag
from app.schemas.follow_up_flag import FollowUpFlagCreate


async def create_flag(
    db: AsyncSession, tenant_id: uuid.UUID, manager_id: uuid.UUID, data: FollowUpFlagCreate
) -> FollowUpFlag:
    flag = FollowUpFlag(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        manager_id=manager_id,
        deal_id=data.deal_id,
        contact_id=data.contact_id,
        note=data.note,
        remind_on=data.remind_on,
    )
    db.add(flag)
    await db.flush()
    await db.refresh(flag)
    return flag


async def list_flags(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    manager_id: uuid.UUID | None,
    contact_id: uuid.UUID | None = None,
) -> list[FollowUpFlag]:
    """manager_id=None means unrestricted (Admin) — REQUIREMENTS.md §4.3:
    this is the manager's own personal tracking list. contact_id narrows
    to one contact's flags — Contact Detail's Follow-up flag card, still
    composed with manager_id so a manager only ever sees their own flag
    on that contact, never a teammate's."""
    stmt = select(FollowUpFlag).where(FollowUpFlag.tenant_id == tenant_id)
    if manager_id is not None:
        stmt = stmt.where(FollowUpFlag.manager_id == manager_id)
    if contact_id is not None:
        stmt = stmt.where(FollowUpFlag.contact_id == contact_id)
    result = await db.execute(stmt.order_by(FollowUpFlag.remind_on))
    return list(result.scalars().all())


async def get_flag(
    db: AsyncSession, tenant_id: uuid.UUID, flag_id: uuid.UUID
) -> FollowUpFlag | None:
    result = await db.execute(
        select(FollowUpFlag).where(
            FollowUpFlag.tenant_id == tenant_id, FollowUpFlag.id == flag_id
        )
    )
    return result.scalar_one_or_none()


async def resolve_flag(db: AsyncSession, flag: FollowUpFlag) -> FollowUpFlag:
    flag.resolved_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(flag)
    return flag
