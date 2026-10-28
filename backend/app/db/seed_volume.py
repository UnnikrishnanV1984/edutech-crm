"""Dev-only idempotent top-up — run after seed.py / seed_runner.py /
seed_ops_data.py on every backend start (ENVIRONMENT=development only,
see docker-entrypoint.sh). seed_ops_data.py seeds a small fixed set of
tasks/escalations/follow-ups once per tenant (gated on "does this tenant
have any SLA policy yet"); this module tops that up toward a larger,
more realistic volume on every run, and spreads deals already ingested
by seed_runner.py across the tenant's full pipeline instead of leaving
every lead sitting at the first stage.

Both halves below are safe to run repeatedly without piling up
duplicates or re-touching rows a previous run already changed:

1. Stage distribution only ever looks at deals still sitting in a
   tenant's first (lowest sort_order) stage — moving a deal out of that
   stage is itself the "already processed" marker, so a later run (after
   seed_data/*.json grows, or a fresh connector run adds leads) only
   touches the newly-ingested ones.
2. Task/flag/escalation top-up checks each tenant's current count
   against a target and only creates the shortfall, so a tenant already
   at target gets nothing more.
"""

import asyncio
import json
import random
import sys
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.db.seed import TENANTS
from app.db.session import get_engine, get_sessionmaker
from app.models.contact import Contact
from app.models.course import Course
from app.models.deal import Deal
from app.models.escalation import Escalation
from app.models.follow_up_flag import FollowUpFlag
from app.models.pipeline_stage import PipelineStage
from app.models.task import Task
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.contact import ContactCreate
from app.schemas.deal import DealCreate
from app.schemas.follow_up_flag import FollowUpFlagCreate
from app.schemas.task import TaskCreate
from app.services import contact_service, deal_service
from app.services.activity_service import log_deal_stage_changed, log_lead_captured
from app.services.escalation_service import (
    create_rule_triggered_escalation,
    create_sla_breach_escalation,
    create_workflow_failure_escalation,
    update_escalation,
)
from app.services.follow_up_flag_service import create_flag
from app.services.task_service import create_task

# A larger, standalone lead pool for making a long-running local dev DB
# look realistically busy — deliberately NOT one of the `source=` =
# seed_data/*.json connector fixtures under app/connectors/, which
# test_connectors_normalize.py and test_ingestion_service.py assert
# exact content/counts against (SEED_CONNECTORS_PLAN.md's golden
# fixtures). Same RawLead-shaped ingestion path as a real lead otherwise
# (contact + deal + activity, deduped by email/phone like any other
# contact), just sourced from this file instead of going through a
# LeadConnector.
EXTRA_LEADS_PATH = Path(__file__).parent / "seed_data" / "extra_leads.json"

if sys.platform == "win32":
    # Same constraint as the other app/db/seed*.py standalone entrypoints.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

TASK_TARGET = 36
FLAG_TARGET = 12
ESCALATION_TARGET = 14

# Course fee guesses, INR — courses carry no price field of their own
# (PIPELINE_AND_REVENUE.md §2.1 only models deal.value), so this is
# purely for giving seeded deals a realistic-looking value once they
# move past Inquiry. Unknown course codes fall back to DEFAULT_FEE.
COURSE_FEE_INR: dict[str, int] = {
    "MBA-FIN": 450_000,
    "DS-202": 85_000,
    "CS-101": 60_000,
    "WEB-BOOT": 70_000,
}
DEFAULT_FEE_INR = 55_000

TASK_TITLES = [
    "Call back about admission query",
    "Send fee structure & brochure",
    "Confirm submitted documents",
    "Schedule counseling call",
    "Follow up on WhatsApp inquiry",
    "Verify entrance exam score",
    "Remind about application deadline",
    "Check in after campus visit",
    "Share scholarship eligibility details",
    "Collect pending KYC documents",
    "Confirm batch start date",
    "Follow up on demo feedback",
]

# Spans overdue / due-today / upcoming / no-due-date, same intent as
# seed_ops_data.py's TASK_DUE_OFFSETS but longer, to cover TASK_TARGET.
TASK_DUE_OFFSETS = [
    timedelta(hours=-30),
    timedelta(days=-3, hours=-2),
    timedelta(hours=-5),
    timedelta(days=-1, hours=-3),
    timedelta(hours=2),
    timedelta(hours=6),
    timedelta(days=1),
    timedelta(days=2),
    timedelta(days=3),
    timedelta(days=5),
    timedelta(days=7),
    None,
]

FOLLOW_UP_NOTES = [
    "Parent asked to be called back after they discuss with family",
    "Waiting on the counselor's promised discount approval",
    "Re-check interest once the next batch dates are announced",
    "Student wants to compare with another institute before deciding",
    "Pending confirmation on hostel availability before enrolling",
    "Asked to follow up after their exam results are out",
    "Waiting on employer sponsorship approval",
    "Requested a callback next week after their current job notice period",
]
FOLLOW_UP_OFFSETS = [-3, -1, 0, 1, 2, 5, 9, 14]

ESCALATION_REASONS = [
    "No response after 3 attempts — need guidance on next step",
    "Needs manager approval for a discount before we can close",
    "Student disputing fee breakdown, escalating for review",
    "Repeated reschedule requests — counselor requesting manager input",
    "Possible duplicate lead, needs manager to confirm ownership",
]


async def _set_tenant(db: AsyncSession, tenant_id: uuid.UUID) -> None:
    await db.execute(
        text("SELECT set_config('app.tenant_id', :tenant_id, true)"), {"tenant_id": str(tenant_id)}
    )


def _pick_new_stage(
    rng: random.Random, stages: list[PipelineStage], current_stage_id: uuid.UUID
) -> PipelineStage | None:
    """Weighted pick, biased like a real admissions funnel: most mass on
    the earlier open stages, a meaningful chunk on won, a smaller chunk
    on lost. 15% of deals are left untouched (still-fresh leads) —
    returns None in that case. Generic over whatever stage set a tenant
    actually has (default 8-stage pipeline or a tenant's own customized
    one), never hardcoded by stage name."""
    if rng.random() < 0.15:
        return None

    candidates = [s for s in stages if s.id != current_stage_id]
    open_stages = sorted(
        (s for s in candidates if not s.is_won and not s.is_lost), key=lambda s: s.sort_order
    )
    won_stages = [s for s in candidates if s.is_won]
    lost_stages = [s for s in candidates if s.is_lost]

    choices: list[PipelineStage] = []
    weights: list[float] = []
    if open_stages:
        raw = [0.6**i for i in range(len(open_stages))]
        raw_sum = sum(raw)
        for stage, w in zip(open_stages, raw, strict=True):
            choices.append(stage)
            weights.append(0.55 * w / raw_sum)
    if won_stages:
        for stage in won_stages:
            choices.append(stage)
            weights.append(0.30 / len(won_stages))
    if lost_stages:
        for stage in lost_stages:
            choices.append(stage)
            weights.append(0.15 / len(lost_stages))

    if not choices:
        return None
    return rng.choices(choices, weights=weights, k=1)[0]


async def _topup_leads(
    db: AsyncSession, tenant_id: uuid.UUID, counselor_ids: list[uuid.UUID]
) -> None:
    """Ingests EXTRA_LEADS_PATH's standalone lead pool the same way a
    real one arrives (contact + deal + lead_captured activity). Safe to
    run every restart: contact_service.create_contact's existing
    email/phone dedupe makes a lead already created on a prior run a
    no-op 409 here, caught and skipped — same dedupe path a genuine
    re-submitted lead would hit."""
    if not EXTRA_LEADS_PATH.exists():
        return
    with EXTRA_LEADS_PATH.open(encoding="utf-8") as f:
        leads = json.load(f)

    course_codes = {lead["course_code"] for lead in leads}
    course_id_by_code: dict[str, uuid.UUID] = {}
    for code in course_codes:
        result = await db.execute(
            select(Course.id).where(Course.tenant_id == tenant_id, Course.code == code)
        )
        course_id = result.scalar_one_or_none()
        if course_id is not None:
            course_id_by_code[code] = course_id

    for i, lead in enumerate(leads):
        course_id = course_id_by_code.get(lead["course_code"])
        if course_id is None:
            continue
        owner_id = counselor_ids[i % len(counselor_ids)]
        try:
            contact = await contact_service.create_contact(
                db,
                tenant_id,
                ContactCreate(
                    full_name=lead["full_name"],
                    email=lead["email"],
                    phone=lead["phone"],
                    lead_source=lead["source"],
                ),
                default_owner_id=owner_id,
            )
        except ApiError:
            continue

        deal = await deal_service.create_deal(
            db, tenant_id, contact.id, DealCreate(course_id=course_id), default_owner_id=owner_id
        )
        await log_lead_captured(
            db,
            tenant_id,
            contact_id=contact.id,
            deal_id=deal.id,
            actor_id=owner_id,
            source=lead["source"],
            external_id=lead["external_id"],
        )


async def _progress_deal_stages(db: AsyncSession, tenant_id: uuid.UUID) -> None:
    stages_result = await db.execute(
        select(PipelineStage)
        .where(PipelineStage.tenant_id == tenant_id)
        .order_by(PipelineStage.sort_order)
    )
    stages = list(stages_result.scalars().all())
    if len(stages) < 2:
        return
    first_stage = stages[0]

    courses_result = await db.execute(select(Course).where(Course.tenant_id == tenant_id))
    fee_by_course_id = {
        c.id: COURSE_FEE_INR.get(c.code, DEFAULT_FEE_INR) for c in courses_result.scalars()
    }

    stuck_result = await db.execute(
        select(Deal).where(Deal.tenant_id == tenant_id, Deal.stage_id == first_stage.id)
    )
    stuck_deals = list(stuck_result.scalars().all())

    for deal in stuck_deals:
        rng = random.Random(f"{tenant_id}:{deal.id}")
        new_stage = _pick_new_stage(rng, stages, deal.stage_id)
        if new_stage is None:
            continue

        old_stage_id = deal.stage_id
        deal.stage_id = new_stage.id
        deal.stage_changed_at = datetime.now(UTC)
        base_fee = fee_by_course_id.get(deal.course_id, DEFAULT_FEE_INR)
        jitter = rng.uniform(0.85, 1.15)
        deal.value = Decimal(str(round(base_fee * jitter, -2)))
        await db.flush()

        await log_deal_stage_changed(
            db,
            tenant_id,
            deal.contact_id,
            deal.id,
            actor_id=deal.owner_id,
            old_stage_id=old_stage_id,
            new_stage_id=new_stage.id,
        )


async def _topup_tasks(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    admin: User,
    assignee_cycle: list[User],
    deals: list[Deal],
    contacts_by_id: dict[uuid.UUID, Contact],
) -> None:
    count_result = await db.execute(
        select(func.count())
        .select_from(Task)
        .where(Task.tenant_id == tenant_id, Task.status == "open")
    )
    shortfall = TASK_TARGET - count_result.scalar_one()
    if shortfall <= 0 or not deals:
        return

    now = datetime.now(UTC)
    for i in range(shortfall):
        deal = deals[i % len(deals)]
        contact = contacts_by_id.get(deal.contact_id)
        if contact is None:
            continue
        offset = TASK_DUE_OFFSETS[i % len(TASK_DUE_OFFSETS)]
        assignee = assignee_cycle[i % len(assignee_cycle)]
        await create_task(
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


async def _topup_follow_up_flags(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    admin: User,
    deals: list[Deal],
) -> None:
    count_result = await db.execute(
        select(func.count()).select_from(FollowUpFlag).where(
            FollowUpFlag.tenant_id == tenant_id, FollowUpFlag.resolved_at.is_(None)
        )
    )
    shortfall = FLAG_TARGET - count_result.scalar_one()
    if shortfall <= 0 or not deals:
        return

    now = datetime.now(UTC)
    for i in range(shortfall):
        deal = deals[(i * 3) % len(deals)]
        note = FOLLOW_UP_NOTES[i % len(FOLLOW_UP_NOTES)]
        day_offset = FOLLOW_UP_OFFSETS[i % len(FOLLOW_UP_OFFSETS)]
        await create_flag(
            db,
            tenant_id,
            admin.id,
            FollowUpFlagCreate(
                deal_id=deal.id, note=note, remind_on=(now + timedelta(days=day_offset)).date()
            ),
        )


async def _topup_escalations(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    admin: User,
    counselor: User,
    deals: list[Deal],
    tasks: list[Task],
) -> None:
    count_result = await db.execute(
        select(func.count()).select_from(Escalation).where(Escalation.tenant_id == tenant_id)
    )
    shortfall = ESCALATION_TARGET - count_result.scalar_one()
    if shortfall <= 0 or not deals:
        return

    for i in range(shortfall):
        kind = i % 4
        if kind == 0:
            db.add(
                Escalation(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    source="manual",
                    deal_id=deals[i % len(deals)].id,
                    raised_by=counselor.id,
                    assigned_to=admin.id,
                    reason=ESCALATION_REASONS[i % len(ESCALATION_REASONS)],
                )
            )
            await db.flush()
        elif kind == 1 and tasks:
            escalation = await create_sla_breach_escalation(
                db,
                tenant_id,
                sla_state_id=uuid.uuid4(),
                deal_id=None,
                task_id=tasks[i % len(tasks)].id,
                assigned_to=admin.id,
            )
            if i % 2 == 0:
                await update_escalation(
                    db, escalation, status="acknowledged", resolution_note=None, reassign_to=None,
                    actor_id=admin.id,
                )
        elif kind == 2:
            escalation = await create_workflow_failure_escalation(
                db,
                tenant_id,
                workflow_run_id=uuid.uuid4(),
                deal_id=deals[i % len(deals)].id,
                task_id=None,
                assigned_to=admin.id,
            )
            escalation = await update_escalation(
                db, escalation, status="acknowledged", resolution_note=None, reassign_to=None,
                actor_id=admin.id,
            )
            if i % 2 == 0:
                await update_escalation(
                    db,
                    escalation,
                    status="resolved",
                    resolution_note="Reassigned lead to backup counselor",
                    reassign_to=None,
                    actor_id=admin.id,
                )
        else:
            escalation = await create_rule_triggered_escalation(
                db,
                tenant_id,
                workflow_run_id=uuid.uuid4(),
                deal_id=deals[i % len(deals)].id,
                task_id=None,
                assigned_to=admin.id,
            )
            if i % 3 == 0:
                await update_escalation(
                    db, escalation, status="resolved",
                    resolution_note="Resolved after manager follow-up",
                    reassign_to=None, actor_id=admin.id,
                )


async def _seed_tenant(db: AsyncSession, tenant_id: uuid.UUID) -> None:
    await _set_tenant(db, tenant_id)

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

    await _topup_leads(db, tenant_id, [u.id for u in counselors])
    await _progress_deal_stages(db, tenant_id)

    deals_result = await db.execute(
        select(Deal).where(Deal.tenant_id == tenant_id).order_by(Deal.created_at).limit(300)
    )
    deals = list(deals_result.scalars().all())
    if not deals:
        return
    contact_ids = [deal.contact_id for deal in deals]
    contacts_result = await db.execute(
        select(Contact).where(Contact.tenant_id == tenant_id, Contact.id.in_(contact_ids))
    )
    contacts_by_id = {c.id: c for c in contacts_result.scalars().all()}

    await _topup_tasks(db, tenant_id, admin, assignee_cycle, deals, contacts_by_id)

    tasks_result = await db.execute(
        select(Task).where(Task.tenant_id == tenant_id).order_by(Task.created_at.desc()).limit(50)
    )
    tasks = list(tasks_result.scalars().all())

    await _topup_follow_up_flags(db, tenant_id, admin, deals)
    await _topup_escalations(db, tenant_id, admin, counselors[0], deals, tasks)


async def seed_volume() -> None:
    # Scoped to the two real dev tenants (keycloak/realm-export.json's
    # seed identities log into these and only these) rather than every
    # row in `tenants` — a long-running local DB accumulates extra
    # tenants from other dev/test flows over time, and there's no real
    # user who'd ever see data seeded into those.
    seed_tenant_ids = {uuid.UUID(tenant_id) for tenant_id, _slug, _name in TENANTS}
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as db:
        result = await db.execute(
            select(Tenant.id).where(Tenant.status == "active", Tenant.id.in_(seed_tenant_ids))
        )
        tenant_ids = list(result.scalars().all())

    for tenant_id in tenant_ids:
        async with sessionmaker() as db, db.begin():
            await _seed_tenant(db, tenant_id)
    await get_engine().dispose()


def main() -> None:
    asyncio.run(seed_volume())


if __name__ == "__main__":
    main()
