import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contact import Contact
from app.models.deal import Deal
from app.models.task import Task
from app.models.workflow_rule import WorkflowRule
from app.models.workflow_run import WorkflowRun
from app.schemas.workflow_rule import WorkflowRuleCreate, WorkflowRuleDecision


async def create_rule(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    created_by: uuid.UUID,
    created_by_role: str,
    data: WorkflowRuleCreate,
) -> WorkflowRule:
    """A Manager's request is always forced to pending_approval regardless
    of what status the request body asked for — REQUIREMENTS.md §2.4,
    never trusted from the client (PHASE_3_PLAN.md §7.3)."""
    status = "pending_approval" if created_by_role == "manager" else data.status
    rule = WorkflowRule(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name=data.name,
        trigger_type=data.trigger_type,
        trigger_config=data.trigger_config,
        conditions=data.conditions,
        actions=data.actions,
        status=status,
        created_by=created_by,
    )
    db.add(rule)
    await db.flush()
    await db.refresh(rule)
    return rule


async def list_rules(
    db: AsyncSession, tenant_id: uuid.UUID, caller_role: str, caller_id: uuid.UUID
) -> list[WorkflowRule]:
    stmt = select(WorkflowRule).where(WorkflowRule.tenant_id == tenant_id)
    if caller_role != "admin":
        # Own proposals (any status) plus every active rule, read-only
        # for the latter — PHASE_3_PLAN.md §7.3.
        stmt = stmt.where(
            or_(WorkflowRule.created_by == caller_id, WorkflowRule.status == "active")
        )
    result = await db.execute(stmt.order_by(WorkflowRule.created_at.desc()))
    return list(result.scalars().all())


async def get_rule(
    db: AsyncSession, tenant_id: uuid.UUID, rule_id: uuid.UUID
) -> WorkflowRule | None:
    result = await db.execute(
        select(WorkflowRule).where(WorkflowRule.tenant_id == tenant_id, WorkflowRule.id == rule_id)
    )
    return result.scalar_one_or_none()


async def get_active_rules_by_trigger(
    db: AsyncSession, tenant_id: uuid.UUID, trigger_type: str
) -> list[WorkflowRule]:
    """Used by app/workers/rules.py — only 'active' rules ever execute."""
    result = await db.execute(
        select(WorkflowRule).where(
            WorkflowRule.tenant_id == tenant_id,
            WorkflowRule.status == "active",
            WorkflowRule.trigger_type == trigger_type,
        )
    )
    return list(result.scalars().all())


async def decide_rule(
    db: AsyncSession, rule: WorkflowRule, admin_id: uuid.UUID, data: WorkflowRuleDecision
) -> WorkflowRule:
    updates = data.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(rule, key, value)
    if "status" in updates and updates["status"] == "active":
        rule.approved_by = admin_id
    await db.flush()
    await db.refresh(rule)
    return rule


# --- Condition matching — shared by app/workers/rules.py's live engine and
# test_run_rule below (OPENFUNNEL_REBRAND_PLAN.md Phase 7g), so "what a
# rule would match" is always exactly what the live engine would have
# matched, not a second reimplementation that could drift. Lives here
# rather than in app/workers/rules.py so the FastAPI process (test-run) can
# import it without pulling in Celery task registration.


def matches_conditions(conditions: list[dict], fields: dict) -> bool:
    """AND-only (PHASE_3_PLAN.md §3.7) — every condition must match."""
    for condition in conditions:
        field, op, value = condition["field"], condition["op"], condition["value"]
        actual = fields.get(field)
        if op == "eq" and actual != value:
            return False
        if op == "in" and actual not in value:
            return False
    return True


async def load_deal(db: AsyncSession, tenant_id: uuid.UUID, deal_id: uuid.UUID) -> Deal | None:
    result = await db.execute(select(Deal).where(Deal.tenant_id == tenant_id, Deal.id == deal_id))
    return result.scalar_one_or_none()


async def load_contact(
    db: AsyncSession, tenant_id: uuid.UUID, contact_id: uuid.UUID
) -> Contact | None:
    result = await db.execute(
        select(Contact).where(Contact.tenant_id == tenant_id, Contact.id == contact_id)
    )
    return result.scalar_one_or_none()


async def load_condition_fields(
    db: AsyncSession, tenant_id: uuid.UUID, source_type: str, source_id: uuid.UUID
) -> dict:
    """task/elapsed_time-adjacent source types intentionally return {} —
    there's no condition-matchable field defined for them yet, so a
    condition on those triggers never matches (same behavior the live
    engine already has, not a test-run-only limitation)."""
    if source_type == "deal":
        deal = await load_deal(db, tenant_id, source_id)
        if deal is None:
            return {}
        return {"stage_id": str(deal.stage_id), "course_id": str(deal.course_id)}
    if source_type == "contact":
        contact = await load_contact(db, tenant_id, source_id)
        if contact is None:
            return {}
        return {"lead_source": contact.lead_source}
    return {}


async def list_runs(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    caller_role: str,
    caller_id: uuid.UUID,
    rule_id: uuid.UUID | None,
    page: int,
    page_size: int,
) -> tuple[list[tuple[WorkflowRun, str]], int]:
    """Returns (rows, total) where each row is (run, rule_name) — joined so
    the Run History view never has to N+1 for the rule's display name.
    Visibility mirrors list_rules exactly: a non-Admin only sees runs for
    rules they created or that are currently active."""
    join_on = (WorkflowRule.id == WorkflowRun.workflow_rule_id) & (
        WorkflowRule.tenant_id == WorkflowRun.tenant_id
    )
    conditions = [WorkflowRun.tenant_id == tenant_id]
    if rule_id is not None:
        conditions.append(WorkflowRun.workflow_rule_id == rule_id)
    if caller_role != "admin":
        conditions.append(
            or_(WorkflowRule.created_by == caller_id, WorkflowRule.status == "active")
        )

    count_stmt = (
        select(func.count(WorkflowRun.id)).select_from(WorkflowRun).join(WorkflowRule, join_on)
        .where(*conditions)
    )
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        select(WorkflowRun, WorkflowRule.name)
        .select_from(WorkflowRun)
        .join(WorkflowRule, join_on)
        .where(*conditions)
        .order_by(WorkflowRun.executed_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(stmt)).all()
    return [(run, rule_name) for run, rule_name in rows], total


_TEST_RUN_CANDIDATE_LIMIT = 20


async def test_run_rule(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    trigger_type: str,
    trigger_config: dict,
    conditions: list[dict],
) -> dict:
    """Read-only dry run — reuses matches_conditions/load_condition_fields
    (the exact logic the live engine uses) against a sample of the
    tenant's own recent/currently-eligible records, without saving the
    rule or executing a single action. Works against a draft (unsaved)
    rule body, matching Phase 7g's acceptance criterion that Test run
    doesn't require saving first."""
    candidates: list[tuple[str, uuid.UUID, str]] = []  # (source_type, id, label)

    if trigger_type == "lead_created":
        contacts = (
            await db.execute(
                select(Contact)
                .where(Contact.tenant_id == tenant_id)
                .order_by(Contact.created_at.desc())
                .limit(_TEST_RUN_CANDIDATE_LIMIT)
            )
        ).scalars().all()
        candidates = [("contact", c.id, c.full_name) for c in contacts]

    elif trigger_type == "stage_changed":
        rows = (
            await db.execute(
                select(Deal.id, Contact.full_name)
                .select_from(Deal)
                .join(Contact, (Contact.id == Deal.contact_id) & (Contact.tenant_id == tenant_id))
                .where(Deal.tenant_id == tenant_id)
                .order_by(Deal.stage_changed_at.desc())
                .limit(_TEST_RUN_CANDIDATE_LIMIT)
            )
        ).all()
        candidates = [("deal", deal_id, contact_name) for deal_id, contact_name in rows]

    elif trigger_type == "elapsed_time":
        since_field = trigger_config.get("since", "stage_entered_at")
        minutes = trigger_config.get("minutes", 0)
        if since_field == "assigned_at":
            return {"candidates_checked": 0, "matched": []}
        cutoff = datetime.now(UTC) - timedelta(minutes=minutes)
        rows = (
            await db.execute(
                select(Deal.id, Contact.full_name)
                .select_from(Deal)
                .join(Contact, (Contact.id == Deal.contact_id) & (Contact.tenant_id == tenant_id))
                .where(Deal.tenant_id == tenant_id, Deal.stage_changed_at <= cutoff)
                .order_by(Deal.stage_changed_at.desc())
                .limit(_TEST_RUN_CANDIDATE_LIMIT)
            )
        ).all()
        candidates = [("deal", deal_id, contact_name) for deal_id, contact_name in rows]

    elif trigger_type == "task_overdue":
        now = datetime.now(UTC)
        tasks = (
            await db.execute(
                select(Task)
                .where(
                    Task.tenant_id == tenant_id,
                    Task.status == "open",
                    Task.due_at.is_not(None),
                    Task.due_at <= now,
                )
                .order_by(Task.due_at.desc())
                .limit(_TEST_RUN_CANDIDATE_LIMIT)
            )
        ).scalars().all()
        candidates = [("task", t.id, t.title) for t in tasks]

    matches = []
    for source_type, source_id, label in candidates:
        fields = await load_condition_fields(db, tenant_id, source_type, source_id)
        if matches_conditions(conditions, fields):
            matches.append({"type": source_type, "id": str(source_id), "label": label})

    return {"candidates_checked": len(candidates), "matched": matches}
