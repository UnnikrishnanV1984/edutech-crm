import uuid
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import VALIDATION_ERROR, ApiError
from app.models.contact import Contact
from app.models.deal import Deal
from app.models.follow_up_flag import FollowUpFlag
from app.models.user import User
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


async def snooze_flag(db: AsyncSession, flag: FollowUpFlag, remind_on: date) -> FollowUpFlag:
    if flag.resolved_at is not None:
        raise ApiError(400, VALIDATION_ERROR, "Cannot snooze a resolved follow-up flag")
    if remind_on <= date.today():
        raise ApiError(400, VALIDATION_ERROR, "snoozed remind_on must be in the future")
    flag.remind_on = remind_on
    await db.flush()
    await db.refresh(flag)
    return flag


async def enrich_flags(
    db: AsyncSession, tenant_id: uuid.UUID, flags: list[FollowUpFlag]
) -> dict[uuid.UUID, dict]:
    """Batch-resolves the queue/board's display data — same batch-enrich
    shape as escalation_service.enrich_escalations. Returns
    {flag_id: {resolved_contact_id, contact_name, manager_name}}."""
    if not flags:
        return {}

    deal_ids = {f.deal_id for f in flags if f.deal_id is not None}
    deal_contact: dict[uuid.UUID, uuid.UUID] = {}
    if deal_ids:
        rows = await db.execute(
            select(Deal.id, Deal.contact_id).where(
                Deal.tenant_id == tenant_id, Deal.id.in_(deal_ids)
            )
        )
        deal_contact = dict(rows.all())

    contact_ids = {f.contact_id for f in flags if f.contact_id is not None} | set(
        deal_contact.values()
    )
    contact_names: dict[uuid.UUID, str] = {}
    if contact_ids:
        rows = await db.execute(
            select(Contact.id, Contact.full_name).where(
                Contact.tenant_id == tenant_id, Contact.id.in_(contact_ids)
            )
        )
        contact_names = dict(rows.all())

    manager_ids = {f.manager_id for f in flags}
    managers = await db.execute(
        select(User).where(User.tenant_id == tenant_id, User.id.in_(manager_ids))
    )
    manager_names = {u.id: (u.full_name or u.email) for u in managers.scalars().all()}

    enrichment: dict[uuid.UUID, dict] = {}
    for flag in flags:
        resolved_contact_id = flag.contact_id or (
            deal_contact.get(flag.deal_id) if flag.deal_id else None
        )
        enrichment[flag.id] = {
            "resolved_contact_id": resolved_contact_id,
            "contact_name": contact_names.get(resolved_contact_id) if resolved_contact_id else None,
            "manager_name": manager_names.get(flag.manager_id),
        }
    return enrichment
