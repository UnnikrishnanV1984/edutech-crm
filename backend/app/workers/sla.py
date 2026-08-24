"""SLA state computation — PHASE_3_PLAN.md §6. Runs on a 5-minute Celery
Beat schedule (celery_app.py), never on-demand at page load
(REQUIREMENTS.md §3.2). Every task takes tenant_id as an explicit,
required first argument (CLAUDE.md rule 6) and sets app.tenant_id itself
at the top of its own transaction — it has no request-scoped session to
inherit one from.

task_type on sla_policies is accepted by the schema for forward
compatibility but has no effect yet: Task has no category/type column
to match against, so a task_due policy applies to every open task with
a due_at regardless of what task_type it names. Multiple active
task_due policies for one tenant is a supported, intentional shape (an
independent SLA clock per policy on the same task), not a bug.
"""

import asyncio
import uuid
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.logging import get_logger
from app.db.session import get_sessionmaker
from app.models.deal import Deal
from app.models.sla_policy import SlaPolicy
from app.models.sla_state import SlaState
from app.models.task import Task
from app.models.tenant import Tenant
from app.models.tenant_sla_settings import TenantSlaSettings
from app.services.business_hours_service import DEFAULT_BUSINESS_HOURS, add_business_minutes
from app.services.escalation_service import create_sla_breach_escalation
from app.services.user_service import get_user
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


async def _set_tenant(db, tenant_id: uuid.UUID) -> None:
    await db.execute(
        text("SELECT set_config('app.tenant_id', :tenant_id, true)"), {"tenant_id": str(tenant_id)}
    )


async def _load_business_hours(db, tenant_id: uuid.UUID) -> tuple[dict, list, str]:
    result = await db.execute(
        select(TenantSlaSettings).where(TenantSlaSettings.tenant_id == tenant_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return DEFAULT_BUSINESS_HOURS, [], "UTC"
    return row.business_hours, row.holidays, row.timezone


def _classify(now: datetime, warning_at: datetime, target_at: datetime) -> str:
    if now >= target_at:
        return "breached"
    if now >= warning_at:
        return "at_risk"
    return "on_track"


async def _upsert_sla_state(
    db,
    tenant_id: uuid.UUID,
    policy: SlaPolicy,
    deal_id: uuid.UUID | None,
    task_id: uuid.UUID | None,
    anchor_at: datetime,
    target_at: datetime,
    warning_at: datetime,
    now: datetime,
) -> tuple[uuid.UUID, str, bool]:
    """Returns (sla_state_id, state, is_new_breach) — is_new_breach is
    True only on the transition INTO breached, so the caller raises
    exactly one escalation per breach, not one per tick."""
    state = _classify(now, warning_at, target_at)
    existing = await db.execute(
        select(SlaState).where(
            SlaState.tenant_id == tenant_id,
            SlaState.sla_policy_id == policy.id,
            SlaState.deal_id == deal_id,
            SlaState.task_id == task_id,
        )
    )
    row = existing.scalar_one_or_none()
    was_breached = row is not None and row.state == "breached"

    stmt = pg_insert(SlaState).values(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        sla_policy_id=policy.id,
        deal_id=deal_id,
        task_id=task_id,
        target_at=target_at,
        warning_at=warning_at,
        state=state,
        breached_at=now if state == "breached" else None,
        computed_at=now,
    ).on_conflict_do_update(
        index_elements=[
            SlaState.tenant_id,
            SlaState.sla_policy_id,
            SlaState.deal_id,
            SlaState.task_id,
        ],
        set_={
            "state": state,
            "computed_at": now,
            "breached_at": text("CASE WHEN excluded.state = 'breached' "
                                 "THEN COALESCE(sla_states.breached_at, excluded.computed_at) "
                                 "ELSE NULL END"),
        },
    ).returning(SlaState.id)
    result = await db.execute(stmt)
    sla_state_id = result.scalar_one()
    return sla_state_id, state, (state == "breached" and not was_breached)


@celery_app.task(name="app.workers.sla.compute_sla_states")
def compute_sla_states(tenant_id: str) -> None:
    asyncio.run(_compute_sla_states(uuid.UUID(tenant_id)))


async def _compute_sla_states(tenant_id: uuid.UUID) -> None:
    sessionmaker = get_sessionmaker()
    now = datetime.now(UTC)
    async with sessionmaker() as db, db.begin():
        await _set_tenant(db, tenant_id)
        business_hours, holidays, timezone = await _load_business_hours(db, tenant_id)

        policies_result = await db.execute(
            select(SlaPolicy).where(SlaPolicy.tenant_id == tenant_id, SlaPolicy.status == "active")
        )
        policies = list(policies_result.scalars().all())

        for policy in policies:
            if policy.applies_to == "stage_entry":
                deals_result = await db.execute(
                    select(Deal).where(
                        Deal.tenant_id == tenant_id, Deal.stage_id == policy.stage_id
                    )
                )
                for deal in deals_result.scalars().all():
                    target_at = add_business_minutes(
                        deal.stage_changed_at,
                        policy.target_minutes,
                        business_hours,
                        holidays,
                        timezone,
                    )
                    warning_minutes = policy.target_minutes * policy.warning_threshold_pct // 100
                    warning_at = add_business_minutes(
                        deal.stage_changed_at, warning_minutes, business_hours, holidays, timezone
                    )
                    sla_state_id, _state, is_new_breach = await _upsert_sla_state(
                        db,
                        tenant_id,
                        policy,
                        deal.id,
                        None,
                        deal.stage_changed_at,
                        target_at,
                        warning_at,
                        now,
                    )
                    if is_new_breach:
                        await _raise_breach_escalation(
                            db, tenant_id, sla_state_id, deal.owner_id, deal.id, None
                        )

            else:  # task_due
                tasks_result = await db.execute(
                    select(Task).where(
                        Task.tenant_id == tenant_id, Task.status == "open", Task.due_at.is_not(None)
                    )
                )
                for task in tasks_result.scalars().all():
                    target_at = task.due_at
                    total_window = (task.due_at - task.created_at).total_seconds()
                    warning_at = task.created_at + (
                        (task.due_at - task.created_at) * policy.warning_threshold_pct / 100
                    ) if total_window > 0 else task.due_at
                    sla_state_id, _state, is_new_breach = await _upsert_sla_state(
                        db,
                        tenant_id,
                        policy,
                        None,
                        task.id,
                        task.created_at,
                        target_at,
                        warning_at,
                        now,
                    )
                    if is_new_breach:
                        await _raise_breach_escalation(
                            db, tenant_id, sla_state_id, task.assignee_id, None, task.id
                        )


async def _raise_breach_escalation(
    db, tenant_id: uuid.UUID, sla_state_id: uuid.UUID, owner_id: uuid.UUID,
    deal_id: uuid.UUID | None, task_id: uuid.UUID | None,
) -> None:
    owner = await get_user(db, tenant_id, owner_id)
    if owner is None or owner.manager_id is None:
        logger.warning(
            "sla_breach_escalation_skipped_no_manager",
            tenant_id=str(tenant_id), owner_id=str(owner_id),
        )
        return
    await create_sla_breach_escalation(
        db, tenant_id, sla_state_id, deal_id, task_id, owner.manager_id
    )


@celery_app.task(name="app.workers.sla.dispatch_sla_computation")
def dispatch_sla_computation() -> None:
    asyncio.run(_dispatch_sla_computation())


async def _dispatch_sla_computation() -> None:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as db:
        result = await db.execute(select(Tenant.id).where(Tenant.status == "active"))
        tenant_ids = list(result.scalars().all())
    for tenant_id in tenant_ids:
        compute_sla_states.delay(str(tenant_id))
