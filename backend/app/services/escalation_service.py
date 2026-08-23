import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import CONFLICT, VALIDATION_ERROR, ApiError
from app.models.deal import Deal
from app.models.escalation import Escalation
from app.models.task import Task
from app.models.user import User
from app.schemas.escalation import EscalationCreate

# open -> acknowledged -> resolved is the only forward path this service
# drives; reassignment is handled separately (reassign_to on
# EscalationUpdate), not as a transition into a status value
# (PHASE_3_PLAN.md acceptance criterion 5).
_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "open": {"acknowledged"},
    "acknowledged": {"resolved"},
    "resolved": set(),
}


async def raise_manual_escalation(
    db: AsyncSession, tenant_id: uuid.UUID, raised_by: uuid.UUID, data: EscalationCreate
) -> Escalation:
    """Returns None if data.deal_id/task_id doesn't reference a real row
    in this tenant — the route turns that into a 404, same as every
    other "does the target exist" check in this codebase, rather than
    letting a bad id surface as a raw FK-violation 500."""
    if data.deal_id is not None:
        target_exists = await db.execute(
            select(Deal.id).where(Deal.tenant_id == tenant_id, Deal.id == data.deal_id)
        )
    else:
        target_exists = await db.execute(
            select(Task.id).where(Task.tenant_id == tenant_id, Task.id == data.task_id)
        )
    if target_exists.scalar_one_or_none() is None:
        return None

    result = await db.execute(
        select(User.manager_id).where(User.tenant_id == tenant_id, User.id == raised_by)
    )
    manager_id = result.scalar_one_or_none()
    if manager_id is None:
        raise ApiError(
            409, CONFLICT, "You have no manager assigned — ask an admin to set one before raising"
        )

    escalation = Escalation(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        source="manual",
        deal_id=data.deal_id,
        task_id=data.task_id,
        raised_by=raised_by,
        assigned_to=manager_id,
        reason=data.reason,
    )
    db.add(escalation)
    await db.flush()
    await db.refresh(escalation)
    return escalation


async def list_escalations(
    db: AsyncSession, tenant_id: uuid.UUID, assigned_to: uuid.UUID | None
) -> list[Escalation]:
    """assigned_to=None means unrestricted (Admin) — every other caller
    only ever sees escalations assigned to themselves, which is also
    correctly empty for a Staff caller since assigned_to is never a
    Staff user's id (PHASE_3_PLAN.md §5)."""
    stmt = select(Escalation).where(Escalation.tenant_id == tenant_id)
    if assigned_to is not None:
        stmt = stmt.where(Escalation.assigned_to == assigned_to)
    result = await db.execute(stmt.order_by(Escalation.opened_at.desc()))
    return list(result.scalars().all())


async def get_escalation(
    db: AsyncSession, tenant_id: uuid.UUID, escalation_id: uuid.UUID
) -> Escalation | None:
    result = await db.execute(
        select(Escalation).where(
            Escalation.tenant_id == tenant_id, Escalation.id == escalation_id
        )
    )
    return result.scalar_one_or_none()


async def update_escalation(
    db: AsyncSession,
    escalation: Escalation,
    status: str | None,
    resolution_note: str | None,
    reassign_to: uuid.UUID | None,
) -> Escalation:
    now = datetime.now(UTC)
    if status is not None:
        if status not in _ALLOWED_TRANSITIONS.get(escalation.status, set()):
            raise ApiError(
                400,
                VALIDATION_ERROR,
                f"Cannot transition from {escalation.status} to {status}",
            )
        escalation.status = status
        if status == "acknowledged":
            escalation.acknowledged_at = now
        elif status == "resolved":
            escalation.resolved_at = now
        if resolution_note is not None:
            escalation.resolution_note = resolution_note

    if reassign_to is not None:
        if escalation.status == "resolved":
            raise ApiError(400, VALIDATION_ERROR, "Cannot reassign a resolved escalation")
        escalation.assigned_to = reassign_to
        escalation.status = "open"
        escalation.acknowledged_at = None

    await db.flush()
    await db.refresh(escalation)
    return escalation
