"""Dev-only seed for Tasks / SLA Policies / Escalations / Follow-up flags.

Unlike contacts and deals (populated by app/connectors/seed_runner.py's
fake lead ingestion), nothing creates a task, an SLA policy, an
escalation, or a follow-up flag until a real user does so by hand — so
those four pages are empty on a fresh `docker compose up`. This seeds all
four, using the same service-layer functions the real API routes use
wherever those functions don't require state this dev environment doesn't
have (see the escalation notes below).

Runs after seed.py (tenants + dev staff) and seed_runner.py (contacts +
deals) in docker-entrypoint.sh's development-only block, since it depends
on both. Skips a tenant entirely if it already has any SLA policies — the
signal this has already run for that tenant — rather than tracking
per-row idempotency keys the way seed_runner.py's Redis-backed lead
ingestion does; ops data doesn't need that granularity.
"""

import asyncio
import sys
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_engine, get_sessionmaker
from app.models.contact import Contact
from app.models.deal import Deal
from app.models.escalation import Escalation
from app.models.pipeline_stage import PipelineStage
from app.models.sla_policy import SlaPolicy
from app.models.task import Task
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.follow_up_flag import FollowUpFlagCreate
from app.schemas.sla_policy import SlaPolicyCreate
from app.schemas.task import TaskCreate
from app.services.escalation_service import (
    create_rule_triggered_escalation,
    create_sla_breach_escalation,
    create_workflow_failure_escalation,
    update_escalation,
)
from app.services.follow_up_flag_service import create_flag
from app.services.sla_policy_service import create_policy
from app.services.task_service import create_task

if sys.platform == "win32":
    # Same constraint as app/db/seed.py and app/connectors/seed_runner.py
    # — this module is its own standalone async entrypoint.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

TASK_TITLES = [
    "Call back about admission query",
    "Send fee structure & brochure",
    "Confirm submitted documents",
    "Schedule counseling call",
    "Follow up on WhatsApp inquiry",
    "Verify entrance exam score",
    "Remind about application deadline",
    "Check in after campus visit",
]

# Offsets from "now" — deliberately spans overdue / due-today / upcoming /
# no-due-date so TasksPage's grouping (Overdue, Today, Upcoming) all have
# something in them.
TASK_DUE_OFFSETS = [
    timedelta(hours=-5),
    timedelta(days=-1, hours=-3),
    timedelta(hours=2),
    timedelta(hours=6),
    timedelta(days=2),
    timedelta(days=5),
    None,
    timedelta(days=1),
]


async def _set_tenant(db: AsyncSession, tenant_id: uuid.UUID) -> None:
    await db.execute(
        text("SELECT set_config('app.tenant_id', :tenant_id, true)"), {"tenant_id": str(tenant_id)}
    )


async def _seed_tenant(db: AsyncSession, tenant_id: uuid.UUID) -> None:
    await _set_tenant(db, tenant_id)

    already_seeded = await db.execute(
        select(SlaPolicy.id).where(SlaPolicy.tenant_id == tenant_id).limit(1)
    )
    if already_seeded.scalar_one_or_none() is not None:
        return

    admin_result = await db.execute(
        select(User).where(User.tenant_id == tenant_id, User.role == "admin").limit(1)
    )
    admin = admin_result.scalar_one_or_none()
    if admin is None:
        return

    counselors_result = await db.execute(
        select(User).where(User.tenant_id == tenant_id, User.role == "counselor")
    )
    counselors = list(counselors_result.scalars().all()) or [admin]
    assignee_cycle = counselors + [admin]

    deals_result = await db.execute(
        select(Deal).where(Deal.tenant_id == tenant_id).order_by(Deal.created_at).limit(10)
    )
    deals = list(deals_result.scalars().all())
    if not deals:
        return
    contact_ids = [deal.contact_id for deal in deals]
    contacts_result = await db.execute(
        select(Contact).where(Contact.tenant_id == tenant_id, Contact.id.in_(contact_ids))
    )
    contacts_by_id = {c.id: c for c in contacts_result.scalars().all()}

    stages_result = await db.execute(
        select(PipelineStage)
        .where(PipelineStage.tenant_id == tenant_id)
        .order_by(PipelineStage.sort_order)
    )
    stages = list(stages_result.scalars().all())
    open_stage = next((s for s in stages if not s.is_won and not s.is_lost), None)

    # --- SLA policies ---------------------------------------------------
    await create_policy(
        db,
        tenant_id,
        SlaPolicyCreate(
            name="First response within 1 hour", applies_to="task_due", target_minutes=60
        ),
    )
    if open_stage is not None:
        await create_policy(
            db,
            tenant_id,
            SlaPolicyCreate(
                name=f"Move out of {open_stage.name} within 4 hours",
                applies_to="stage_entry",
                stage_id=open_stage.id,
                target_minutes=240,
                warning_threshold_pct=75,
            ),
        )
    legacy_policy = await create_policy(
        db,
        tenant_id,
        SlaPolicyCreate(
            name="Legacy: respond within 24 hours", applies_to="task_due", target_minutes=1440
        ),
    )
    legacy_policy.status = "disabled"

    # --- Tasks ------------------------------------------------------------
    now = datetime.now(UTC)
    tasks: list[Task] = []
    for i, offset in enumerate(TASK_DUE_OFFSETS):
        deal = deals[i % len(deals)]
        contact = contacts_by_id.get(deal.contact_id)
        if contact is None:
            continue
        assignee = assignee_cycle[i % len(assignee_cycle)]
        task = await create_task(
            db,
            tenant_id,
            TaskCreate(
                contact_id=contact.id,
                deal_id=deal.id,
                assignee_id=assignee.id,
                title=f"{TASK_TITLES[i % len(TASK_TITLES)]} — {contact.full_name}",
                due_at=(now + offset) if offset is not None else None,
            ),
            default_assignee_id=admin.id,
        )
        tasks.append(task)

    # --- Follow-up flags ----------------------------------------------
    # manager_id is whoever creates the flag (admin here) — the API allows
    # both manager and admin, no separate "manager" role exists in the dev
    # realm's seeded users.
    follow_up_notes = [
        ("Parent asked to be called back after they discuss with family", -2),
        ("Waiting on the counselor's promised discount approval", 1),
        ("Re-check interest once the next batch dates are announced", 5),
    ]
    for i, (note, day_offset) in enumerate(follow_up_notes):
        deal = deals[i % len(deals)]
        await create_flag(
            db,
            tenant_id,
            admin.id,
            FollowUpFlagCreate(
                deal_id=deal.id, note=note, remind_on=(now + timedelta(days=day_offset)).date()
            ),
        )

    # --- Escalations ----------------------------------------------------
    # Manual escalations are built directly rather than via
    # escalation_service.raise_manual_escalation: that function requires
    # the raiser to already have a manager assigned (409s otherwise), and
    # the dev realm has no "manager" role user for counselors to report
    # to. The other three sources have no such precondition, so those go
    # through the real service functions app/workers/*.py uses.
    counselor = counselors[0]
    db.add(
        Escalation(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            source="manual",
            deal_id=deals[0].id,
            raised_by=counselor.id,
            assigned_to=admin.id,
            reason="No response after 3 attempts — need guidance on next step",
        )
    )
    if tasks:
        await create_sla_breach_escalation(
            db,
            tenant_id,
            sla_state_id=uuid.uuid4(),
            deal_id=None,
            task_id=tasks[0].id,
            assigned_to=admin.id,
        )
    workflow_failure = await create_workflow_failure_escalation(
        db,
        tenant_id,
        workflow_run_id=uuid.uuid4(),
        deal_id=deals[min(1, len(deals) - 1)].id,
        task_id=None,
        assigned_to=admin.id,
    )
    await update_escalation(
        db, workflow_failure, status="acknowledged", resolution_note=None, reassign_to=None,
        actor_id=admin.id,
    )
    if len(tasks) > 1:
        rule_triggered = await create_rule_triggered_escalation(
            db,
            tenant_id,
            workflow_run_id=uuid.uuid4(),
            deal_id=None,
            task_id=tasks[-1].id,
            assigned_to=admin.id,
        )
        rule_triggered = await update_escalation(
            db, rule_triggered, status="acknowledged", resolution_note=None, reassign_to=None,
            actor_id=admin.id,
        )
        await update_escalation(
            db,
            rule_triggered,
            status="resolved",
            resolution_note="Reassigned lead to backup counselor",
            reassign_to=None,
            actor_id=admin.id,
        )
    db.add(
        Escalation(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            source="manual",
            deal_id=deals[min(2, len(deals) - 1)].id,
            raised_by=counselor.id,
            assigned_to=admin.id,
            reason="Needs manager approval for a discount before we can close",
        )
    )


async def seed_ops_data() -> None:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as db:
        result = await db.execute(select(Tenant.id).where(Tenant.status == "active"))
        tenant_ids = list(result.scalars().all())

    for tenant_id in tenant_ids:
        async with sessionmaker() as db, db.begin():
            await _seed_tenant(db, tenant_id)
    await get_engine().dispose()


def main() -> None:
    asyncio.run(seed_ops_data())


if __name__ == "__main__":
    main()
