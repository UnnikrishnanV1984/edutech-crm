"""Workflow rule engine — PHASE_3_PLAN.md §7. Event-triggered rules are
enqueued by their write-path (deal stage-change route, Phase 2's
ingestion paths) right after that transaction commits; time-based rules
are scanned on the same 5-minute Beat schedule as SLA computation
(celery_app.py). Every task takes tenant_id as an explicit, required
first argument (CLAUDE.md rule 6).

Each rule executes in its OWN short transaction against its own fresh
session — the same "one bad unit of work can't poison the batch"
principle app/connectors/ingestion_service.py already established for
seeded leads. This matters more here than it might look: if multiple
rules shared one transaction and a later rule raised, an earlier rule's
already-"successful" action (e.g. a created task) would roll back too,
then re-execute and duplicate itself on retry. Per-rule transactions
avoid that entirely. Retries likewise happen as a local loop within one
rule's handling, not as a whole-task Celery retry that would re-run
every other rule in the batch alongside the one that actually failed.

workflow_runs is one row per (rule, trigger source) — not one row per
action. A rule whose actions include send_message therefore can't
partially succeed at the row-status level: if any action is
send_message, the whole run is recorded skipped_unavailable (after
still executing every other action in the list) rather than inventing
a finer-grained status shape the schema doesn't have.
"""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.logging import get_logger
from app.core.redis import get_redis_client
from app.db.session import get_sessionmaker
from app.models.activity import Activity
from app.models.deal import Deal
from app.models.task import Task
from app.models.tenant import Tenant
from app.models.user import User
from app.models.workflow_rule import WorkflowRule
from app.models.workflow_run import WorkflowRun
from app.schemas.task import TaskCreate
from app.services import activity_service, task_service
from app.services.escalation_service import (
    create_rule_triggered_escalation,
    create_workflow_failure_escalation,
)
from app.services.user_service import get_user, list_counselor_ids
from app.services.workflow_rule_service import (
    get_active_rules_by_trigger,
    load_condition_fields,
    load_contact,
    load_deal,
    matches_conditions,
)
from app.workers.celery_app import celery_app

logger = get_logger(__name__)

_MAX_ATTEMPTS = 3


class RaiseEscalationRequested(Exception):
    """Not a real error — a signal from _execute_action back to the
    caller that a raise_escalation action fired, carrying what's needed
    to create the escalation row once the workflow_runs id exists.
    Using an exception as a return channel here is unusual; the
    alternative (threading an extra mutable-result parameter through
    _execute_action for one action type out of six) seemed worse."""

    def __init__(self, deal_id: uuid.UUID | None, manager_id: uuid.UUID):
        # No contact_id field: escalations has no contact_id column
        # (only deal_id/task_id, PHASE_3_PLAN.md §3.5) — a
        # contact-sourced rule with no deal simply raises with both
        # NULL, which the CHECK constraint permits for this source.
        self.deal_id = deal_id
        self.manager_id = manager_id
        super().__init__("raise_escalation requested")


async def _set_tenant(db, tenant_id: uuid.UUID) -> None:
    await db.execute(
        text("SELECT set_config('app.tenant_id', :tenant_id, true)"), {"tenant_id": str(tenant_id)}
    )


async def _resolve_deal_and_contact(
    db, tenant_id: uuid.UUID, source_type: str, source_id: uuid.UUID
) -> tuple[Deal | None, uuid.UUID | None, uuid.UUID | None]:
    """Returns (deal_or_none, contact_id_or_none, owner_id_or_none)."""
    if source_type == "deal":
        deal = await load_deal(db, tenant_id, source_id)
        if deal is None:
            return None, None, None
        return deal, deal.contact_id, deal.owner_id
    if source_type == "contact":
        contact = await load_contact(db, tenant_id, source_id)
        if contact is None:
            return None, None, None
        return None, contact.id, contact.owner_id
    return None, None, None


async def _next_round_robin_counselor(db, tenant_id: uuid.UUID) -> uuid.UUID | None:
    counselor_ids = await list_counselor_ids(db, tenant_id)
    if not counselor_ids:
        return None
    redis = get_redis_client()
    try:
        index = await redis.incr(f"roundrobin:{tenant_id}:owner")
    finally:
        await redis.aclose()
    return counselor_ids[(index - 1) % len(counselor_ids)]


async def _match_territory_counselor(
    db, tenant_id: uuid.UUID, territory: str
) -> uuid.UUID | None:
    result = await db.execute(
        select(User.id)
        .where(
            User.tenant_id == tenant_id,
            User.role == "counselor",
            User.status == "active",
            User.territory == territory,
        )
        .order_by(User.created_at, User.id)
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _apply_new_owner(
    db, tenant_id: uuid.UUID, deal: Deal | None, contact_id: uuid.UUID | None, new_owner: uuid.UUID
) -> None:
    if deal is not None:
        deal.owner_id = new_owner
    if contact_id is not None:
        contact = await load_contact(db, tenant_id, contact_id)
        if contact is not None:
            contact.owner_id = new_owner
    await db.flush()


async def _execute_action(
    db, tenant_id: uuid.UUID, action: dict, source_type: str, source_id: uuid.UUID
) -> None:
    action_type = action["type"]
    config = action.get("config", {})
    deal, contact_id, owner_id = await _resolve_deal_and_contact(
        db, tenant_id, source_type, source_id
    )

    if action_type == "assign_round_robin":
        new_owner = await _next_round_robin_counselor(db, tenant_id)
        if new_owner is None:
            logger.warning("workflow_action_skipped_no_counselors", tenant_id=str(tenant_id))
            return
        await _apply_new_owner(db, tenant_id, deal, contact_id, new_owner)

    elif action_type == "assign_by_territory":
        # GAP_FIXES_PLAN.md item 3 — admin-set territory on both sides
        # (no connector emits one on a raw lead yet). Falls back to
        # round robin rather than leaving the record unassigned when
        # there's no territory set or no counselor matches it — expected
        # to be the common case today, not an edge case.
        territory = None
        if contact_id is not None:
            contact = await load_contact(db, tenant_id, contact_id)
            territory = contact.territory if contact is not None else None
        new_owner = (
            await _match_territory_counselor(db, tenant_id, territory) if territory else None
        )
        if new_owner is None:
            new_owner = await _next_round_robin_counselor(db, tenant_id)
        if new_owner is None:
            logger.warning("workflow_action_skipped_no_counselors", tenant_id=str(tenant_id))
            return
        await _apply_new_owner(db, tenant_id, deal, contact_id, new_owner)

    elif action_type == "create_task":
        if contact_id is None or owner_id is None:
            raise ValueError("create_task requires a resolvable contact")
        due_at = None
        if "due_in_minutes" in config:
            due_at = datetime.now(UTC) + timedelta(minutes=config["due_in_minutes"])
        await task_service.create_task(
            db,
            tenant_id,
            TaskCreate(
                contact_id=contact_id,
                deal_id=deal.id if deal is not None else None,
                assignee_id=owner_id,
                title=config.get("title", "Follow up"),
                due_at=due_at,
            ),
            default_assignee_id=owner_id,
        )

    elif action_type == "change_stage":
        if deal is None:
            raise ValueError("change_stage requires a deal-sourced trigger")
        old_stage_id = deal.stage_id
        deal.stage_id = uuid.UUID(config["to_stage_id"])
        deal.stage_changed_at = datetime.now(UTC)
        await db.flush()
        await activity_service.log_deal_stage_changed(
            db,
            tenant_id,
            deal.contact_id,
            deal.id,
            actor_id=deal.owner_id,
            old_stage_id=old_stage_id,
            new_stage_id=deal.stage_id,
        )

    elif action_type == "notify_manager":
        if contact_id is None or owner_id is None:
            return
        activity = Activity(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            contact_id=contact_id,
            deal_id=deal.id if deal is not None else None,
            type="workflow_notification",
            actor_id=owner_id,
            payload={"message": config.get("message", "A workflow rule notified you.")},
        )
        db.add(activity)
        await db.flush()

    elif action_type == "raise_escalation":
        if owner_id is None:
            return
        owner = await get_user(db, tenant_id, owner_id)
        if owner is None or owner.manager_id is None:
            logger.warning(
                "workflow_raise_escalation_skipped_no_manager", tenant_id=str(tenant_id)
            )
            return
        raise RaiseEscalationRequested(deal.id if deal is not None else None, owner.manager_id)

    elif action_type == "send_message":
        return  # handled at the run level — see module docstring

    else:  # pragma: no cover — schema validation already rejects this
        raise ValueError(f"unknown action type {action_type}")


async def _already_ran(
    db, tenant_id: uuid.UUID, rule_id: uuid.UUID, source_type: str, source_id: uuid.UUID
) -> bool:
    result = await db.execute(
        select(WorkflowRun.id).where(
            WorkflowRun.tenant_id == tenant_id,
            WorkflowRun.workflow_rule_id == rule_id,
            WorkflowRun.trigger_source_type == source_type,
            WorkflowRun.trigger_source_id == source_id,
            WorkflowRun.status == "success",
        )
    )
    return result.scalar_one_or_none() is not None


async def _record_run(
    db,
    tenant_id: uuid.UUID,
    rule_id: uuid.UUID,
    source_type: str,
    source_id: uuid.UUID,
    status: str,
    attempt: int,
    error_message: str | None = None,
) -> uuid.UUID:
    run_id = uuid.uuid4()
    stmt = pg_insert(WorkflowRun).values(
        id=run_id,
        tenant_id=tenant_id,
        workflow_rule_id=rule_id,
        trigger_source_type=source_type,
        trigger_source_id=source_id,
        status=status,
        attempt=attempt,
        error_message=error_message,
    )
    if status == "success":
        # Matches uq_workflow_runs_dedupe's partial index (alembic 0014).
        stmt = stmt.on_conflict_do_nothing(
            index_elements=[
                WorkflowRun.tenant_id,
                WorkflowRun.workflow_rule_id,
                WorkflowRun.trigger_source_type,
                WorkflowRun.trigger_source_id,
            ],
            index_where=WorkflowRun.status == "success",
        )
    await db.execute(stmt)
    await db.flush()
    return run_id


async def _run_one_rule(
    tenant_id: uuid.UUID, rule: WorkflowRule, source_type: str, source_id: uuid.UUID
) -> None:
    """One rule, one trigger source, its own session/transaction, up to
    _MAX_ATTEMPTS local retries. Never lets one rule's failure affect any
    other rule evaluated for the same event/scan tick."""
    sessionmaker = get_sessionmaker()
    last_error: str | None = None

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            async with sessionmaker() as db, db.begin():
                await _set_tenant(db, tenant_id)

                if await _already_ran(db, tenant_id, rule.id, source_type, source_id):
                    return
                fields = await load_condition_fields(db, tenant_id, source_type, source_id)
                if not matches_conditions(rule.conditions, fields):
                    return

                has_send_message = any(a["type"] == "send_message" for a in rule.actions)
                escalation_request: RaiseEscalationRequested | None = None
                for action in rule.actions:
                    try:
                        await _execute_action(db, tenant_id, action, source_type, source_id)
                    except RaiseEscalationRequested as requested:
                        escalation_request = requested

                status = "skipped_unavailable" if has_send_message else "success"
                run_id = await _record_run(
                    db, tenant_id, rule.id, source_type, source_id, status, attempt
                )
                if escalation_request is not None:
                    await create_rule_triggered_escalation(
                        db,
                        tenant_id,
                        run_id,
                        escalation_request.deal_id,
                        None,
                        escalation_request.manager_id,
                    )
            return  # committed successfully
        except Exception as exc:  # noqa: BLE001 — genuinely any action can raise
            last_error = str(exc)
            logger.warning(
                "workflow_rule_attempt_failed",
                tenant_id=str(tenant_id),
                rule_id=str(rule.id),
                attempt=attempt,
                error=last_error,
            )

    # Exhausted retries — record exactly one failure + one escalation,
    # in a fresh transaction since whatever the last attempt touched may
    # be in a rolled-back, unusable state.
    async with sessionmaker() as db, db.begin():
        await _set_tenant(db, tenant_id)
        run_id = await _record_run(
            db, tenant_id, rule.id, source_type, source_id, "failed", _MAX_ATTEMPTS, last_error
        )
        creator = await get_user(db, tenant_id, rule.created_by)
        assigned_to = creator.manager_id if creator and creator.manager_id else rule.created_by
        await create_workflow_failure_escalation(db, tenant_id, run_id, None, None, assigned_to)


@celery_app.task(name="app.workers.rules.evaluate_event_rules")
def evaluate_event_rules(
    tenant_id: str, trigger_type: str, source_type: str, source_id: str
) -> None:
    asyncio.run(
        _evaluate_event_rules(uuid.UUID(tenant_id), trigger_type, source_type, uuid.UUID(source_id))
    )


async def _evaluate_event_rules(
    tenant_id: uuid.UUID, trigger_type: str, source_type: str, source_id: uuid.UUID
) -> None:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as db, db.begin():
        await _set_tenant(db, tenant_id)
        rules = await get_active_rules_by_trigger(db, tenant_id, trigger_type)
    for rule in rules:
        await _run_one_rule(tenant_id, rule, source_type, source_id)


@celery_app.task(name="app.workers.rules.scan_time_based_rules")
def scan_time_based_rules(tenant_id: str) -> None:
    asyncio.run(_scan_time_based_rules(uuid.UUID(tenant_id)))


async def _scan_time_based_rules(tenant_id: uuid.UUID) -> None:
    sessionmaker = get_sessionmaker()
    now = datetime.now(UTC)

    for trigger_type in ("elapsed_time", "task_overdue"):
        async with sessionmaker() as db, db.begin():
            await _set_tenant(db, tenant_id)
            rules = await get_active_rules_by_trigger(db, tenant_id, trigger_type)

            targets: list[tuple[WorkflowRule, uuid.UUID, str]] = []
            for rule in rules:
                if trigger_type == "elapsed_time":
                    since_field = rule.trigger_config.get("since", "stage_entered_at")
                    minutes = rule.trigger_config.get("minutes", 0)
                    if since_field == "assigned_at":
                        # No assigned_at column exists on deals yet —
                        # flagged rather than silently treated as
                        # stage_entered_at.
                        logger.warning(
                            "workflow_rule_unsupported_since_field",
                            tenant_id=str(tenant_id),
                            rule_id=str(rule.id),
                        )
                        continue
                    cutoff = now - timedelta(minutes=minutes)
                    deals_result = await db.execute(
                        select(Deal.id).where(
                            Deal.tenant_id == tenant_id, Deal.stage_changed_at <= cutoff
                        )
                    )
                    targets.extend((rule, deal_id, "deal") for deal_id in deals_result.scalars())
                else:
                    tasks_result = await db.execute(
                        select(Task.id).where(
                            Task.tenant_id == tenant_id,
                            Task.status == "open",
                            Task.due_at.is_not(None),
                            Task.due_at <= now,
                        )
                    )
                    targets.extend((rule, task_id, "task") for task_id in tasks_result.scalars())

        for rule, target_id, source_type in targets:
            await _run_one_rule(tenant_id, rule, source_type, target_id)


@celery_app.task(name="app.workers.rules.dispatch_time_based_scan")
def dispatch_time_based_scan() -> None:
    asyncio.run(_dispatch_time_based_scan())


async def _dispatch_time_based_scan() -> None:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as db:
        result = await db.execute(select(Tenant.id).where(Tenant.status == "active"))
        tenant_ids = list(result.scalars().all())
    for tenant_id in tenant_ids:
        scan_time_based_rules.delay(str(tenant_id))
