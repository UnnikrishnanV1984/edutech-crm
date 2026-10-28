import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import CONFLICT, VALIDATION_ERROR, ApiError
from app.models.contact import Contact
from app.models.deal import Deal
from app.models.escalation import Escalation
from app.models.sla_policy import SlaPolicy
from app.models.sla_state import SlaState
from app.models.task import Task
from app.models.user import User
from app.models.workflow_rule import WorkflowRule
from app.models.workflow_run import WorkflowRun
from app.schemas.escalation import EscalationCreate
from app.services.audit_log_service import record as record_audit_log

# open -> acknowledged -> resolved is the "worked it" path; open/acknowledged
# -> resolved directly and -> snoozed are both also allowed — REQUIREMENTS.md
# §4.2: "Manager acknowledgement should be fast to do... single action",
# which the resolve drawer's single-submit "Contacted — close"/"Snooze
# until..." outcomes both rely on (OPENFUNNEL_REBRAND_PLAN.md Phase 7e).
# Reassignment is handled separately (reassign_to on EscalationUpdate), not
# as a transition into a status value (PHASE_3_PLAN.md acceptance criterion
# 5). snoozed -> open is not reachable through this table at all — only
# app/workers/escalations.py's expiry scan sets it, directly, once
# snoozed_until passes.
_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "open": {"acknowledged", "resolved", "snoozed"},
    "acknowledged": {"resolved", "snoozed"},
    "resolved": set(),
    "snoozed": set(),
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


async def create_sla_breach_escalation(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    sla_state_id: uuid.UUID,
    deal_id: uuid.UUID | None,
    task_id: uuid.UUID | None,
    assigned_to: uuid.UUID,
) -> Escalation:
    """Called by app/workers/sla.py on a fresh breach transition — never
    from an API route. No manager-existence check here (unlike the
    manual-raise path): the caller (compute_sla_states) already resolved
    assigned_to and logs+skips instead of calling this when there's no
    manager to assign, per PHASE_3_PLAN.md §6."""
    escalation = Escalation(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        source="sla_breach",
        deal_id=deal_id,
        task_id=task_id,
        sla_state_id=sla_state_id,
        assigned_to=assigned_to,
    )
    db.add(escalation)
    await db.flush()
    return escalation


async def create_workflow_failure_escalation(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    workflow_run_id: uuid.UUID,
    deal_id: uuid.UUID | None,
    task_id: uuid.UUID | None,
    assigned_to: uuid.UUID,
) -> Escalation:
    """Called by app/workers/rules.py on final action-retry exhaustion
    (source='workflow_failure') or a raise_escalation action succeeding
    (source='rule_triggered', PHASE_3_PLAN.md §7.4) — the caller picks
    which via the source param below, both share this shape."""
    escalation = Escalation(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        source="workflow_failure",
        deal_id=deal_id,
        task_id=task_id,
        workflow_run_id=workflow_run_id,
        assigned_to=assigned_to,
    )
    db.add(escalation)
    await db.flush()
    return escalation


async def create_rule_triggered_escalation(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    workflow_run_id: uuid.UUID,
    deal_id: uuid.UUID | None,
    task_id: uuid.UUID | None,
    assigned_to: uuid.UUID,
) -> Escalation:
    escalation = Escalation(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        source="rule_triggered",
        deal_id=deal_id,
        task_id=task_id,
        workflow_run_id=workflow_run_id,
        assigned_to=assigned_to,
    )
    db.add(escalation)
    await db.flush()
    return escalation


async def list_escalations(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    assigned_to: uuid.UUID | None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[Escalation], int]:
    """assigned_to=None means unrestricted (Admin) — every other caller
    only ever sees escalations assigned to themselves, which is also
    correctly empty for a Staff caller since assigned_to is never a
    Staff user's id (PHASE_3_PLAN.md §5)."""
    stmt = select(Escalation).where(Escalation.tenant_id == tenant_id)
    if assigned_to is not None:
        stmt = stmt.where(Escalation.assigned_to == assigned_to)
    if status is not None:
        stmt = stmt.where(Escalation.status == status)

    count_result = await db.execute(select(func.count()).select_from(stmt.subquery()))
    total = count_result.scalar_one()

    stmt = (
        stmt.order_by(Escalation.opened_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all()), total


async def enrich_escalations(
    db: AsyncSession, tenant_id: uuid.UUID, escalations: list[Escalation]
) -> dict[uuid.UUID, dict]:
    """Batch-resolves display data the queue/drawer need but the row
    itself doesn't carry: which contact this is about, a human-readable
    rule/policy name, and the assignee's display name. Same batch-enrich
    shape as contact_service's list-view enrichment — a handful of `IN`
    queries against the small distinct-id sets collected below, not one
    query per escalation. Returns {escalation_id: {contact_id,
    contact_name, rule_name, assigned_to_name}}."""
    if not escalations:
        return {}

    deal_ids = {e.deal_id for e in escalations if e.deal_id is not None}
    task_ids = {e.task_id for e in escalations if e.task_id is not None}
    sla_state_ids = {e.sla_state_id for e in escalations if e.sla_state_id is not None}
    workflow_run_ids = {e.workflow_run_id for e in escalations if e.workflow_run_id is not None}
    user_ids = {e.assigned_to for e in escalations}

    deal_contact: dict[uuid.UUID, uuid.UUID] = {}
    if deal_ids:
        rows = await db.execute(
            select(Deal.id, Deal.contact_id).where(
                Deal.tenant_id == tenant_id, Deal.id.in_(deal_ids)
            )
        )
        deal_contact = dict(rows.all())

    task_contact: dict[uuid.UUID, uuid.UUID] = {}
    if task_ids:
        rows = await db.execute(
            select(Task.id, Task.contact_id).where(
                Task.tenant_id == tenant_id, Task.id.in_(task_ids)
            )
        )
        task_contact = dict(rows.all())

    contact_ids = set(deal_contact.values()) | set(task_contact.values())
    contact_names: dict[uuid.UUID, str] = {}
    if contact_ids:
        rows = await db.execute(
            select(Contact.id, Contact.full_name).where(
                Contact.tenant_id == tenant_id, Contact.id.in_(contact_ids)
            )
        )
        contact_names = dict(rows.all())

    sla_policy_name: dict[uuid.UUID, str] = {}
    if sla_state_ids:
        rows = await db.execute(
            select(SlaState.id, SlaPolicy.name)
            .select_from(SlaState)
            .join(
                SlaPolicy,
                (SlaPolicy.id == SlaState.sla_policy_id) & (SlaPolicy.tenant_id == tenant_id),
            )
            .where(SlaState.tenant_id == tenant_id, SlaState.id.in_(sla_state_ids))
        )
        sla_policy_name = dict(rows.all())

    workflow_rule_name: dict[uuid.UUID, str] = {}
    if workflow_run_ids:
        rows = await db.execute(
            select(WorkflowRun.id, WorkflowRule.name)
            .select_from(WorkflowRun)
            .join(
                WorkflowRule,
                (WorkflowRule.id == WorkflowRun.workflow_rule_id)
                & (WorkflowRule.tenant_id == tenant_id),
            )
            .where(WorkflowRun.tenant_id == tenant_id, WorkflowRun.id.in_(workflow_run_ids))
        )
        workflow_rule_name = dict(rows.all())

    users = await db.execute(
        select(User).where(User.tenant_id == tenant_id, User.id.in_(user_ids))
    )
    user_names = {u.id: (u.full_name or u.email) for u in users.scalars().all()}

    enrichment: dict[uuid.UUID, dict] = {}
    for escalation in escalations:
        contact_id = None
        if escalation.deal_id is not None:
            contact_id = deal_contact.get(escalation.deal_id)
        elif escalation.task_id is not None:
            contact_id = task_contact.get(escalation.task_id)

        rule_name = None
        if escalation.sla_state_id is not None:
            rule_name = sla_policy_name.get(escalation.sla_state_id)
        elif escalation.workflow_run_id is not None:
            rule_name = workflow_rule_name.get(escalation.workflow_run_id)

        enrichment[escalation.id] = {
            "contact_id": contact_id,
            "contact_name": contact_names.get(contact_id) if contact_id else None,
            "rule_name": rule_name,
            "assigned_to_name": user_names.get(escalation.assigned_to),
        }
    return enrichment


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
    actor_id: uuid.UUID,
    snoozed_until: datetime | None = None,
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
            # A direct open->resolved skip shouldn't leave acknowledged_at
            # NULL on a terminal row — backfill it to the same timestamp.
            if escalation.acknowledged_at is None:
                escalation.acknowledged_at = now
            escalation.resolved_at = now
        elif status == "snoozed":
            escalation.snoozed_until = snoozed_until
        await record_audit_log(
            db, escalation.tenant_id, actor_id, f"escalation.{status}", "escalation", escalation.id
        )

    # Applies regardless of which branch above fired — previously nested
    # under `if status is not None`, so a reassign-only PATCH silently
    # dropped its note (found while designing Phase 7e's resolve drawer).
    if resolution_note is not None:
        escalation.resolution_note = resolution_note

    if reassign_to is not None:
        if escalation.status == "resolved":
            raise ApiError(400, VALIDATION_ERROR, "Cannot reassign a resolved escalation")
        escalation.assigned_to = reassign_to
        escalation.status = "open"
        escalation.acknowledged_at = None
        escalation.was_reopened = True
        await record_audit_log(
            db,
            escalation.tenant_id,
            actor_id,
            "escalation.reassigned",
            "escalation",
            escalation.id,
            payload={"reassigned_to": str(reassign_to)},
        )

    await db.flush()
    await db.refresh(escalation)
    return escalation
