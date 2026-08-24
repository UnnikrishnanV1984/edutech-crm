import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workflow_rule import WorkflowRule
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
