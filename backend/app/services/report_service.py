"""PHASE_4_PLAN.md §4/§6 — every function is (tenant_id, owner_ids) ->
cache-aside result, reusing app/deps/scope.py's RowScope for role-based
visibility rather than a second scoping system. owner_ids=None means
unrestricted (Admin); everything else filters by it the same way
Phase 3's contact_service/deal_service/task_service already do.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.report_cache import get_or_compute
from app.models.contact import Contact
from app.models.deal import Deal
from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.pipeline_stage import PipelineStage
from app.models.sla_state import SlaState
from app.models.user import User

# Worst-first — matches REQUIREMENTS.md §5.1's "sorted by SLA urgency
# (breached first, then at-risk, then on-track)". A deal with no
# sla_states row yet (no policy has ticked it) sorts last, not dropped.
_SLA_URGENCY_ORDER = {"breached": 0, "at_risk": 1, "on_track": 2}


async def get_funnel(
    db: AsyncSession, tenant_id: uuid.UUID, owner_ids: list[uuid.UUID] | None
) -> tuple[list[dict], str]:
    async def compute() -> list[dict]:
        stages = (
            (
                await db.execute(
                    select(PipelineStage)
                    .where(PipelineStage.tenant_id == tenant_id)
                    .order_by(PipelineStage.sort_order)
                )
            )
            .scalars()
            .all()
        )
        count_stmt = select(
            Deal.stage_id, func.count(Deal.id), func.coalesce(func.sum(Deal.value), 0)
        ).where(Deal.tenant_id == tenant_id)
        if owner_ids is not None:
            count_stmt = count_stmt.where(Deal.owner_id.in_(owner_ids))
        rows = (await db.execute(count_stmt.group_by(Deal.stage_id))).all()
        counts = {stage_id: count for stage_id, count, _value in rows}
        values = {stage_id: value for stage_id, _count, value in rows}
        return [
            {
                "stage_id": str(s.id),
                "stage_name": s.name,
                "count": counts.get(s.id, 0),
                "value": str(values.get(s.id, Decimal("0"))),
            }
            for s in stages
        ]

    return await get_or_compute(tenant_id, "funnel", owner_ids, compute)


async def get_source_attribution(
    db: AsyncSession, tenant_id: uuid.UUID, owner_ids: list[uuid.UUID] | None
) -> tuple[list[dict], str]:
    async def compute() -> list[dict]:
        stmt = select(Contact.lead_source, func.count(Contact.id)).where(
            Contact.tenant_id == tenant_id
        )
        if owner_ids is not None:
            stmt = stmt.where(Contact.owner_id.in_(owner_ids))
        rows = (await db.execute(stmt.group_by(Contact.lead_source))).all()
        return [{"lead_source": source, "count": count} for source, count in rows]

    return await get_or_compute(tenant_id, "source_attribution", owner_ids, compute)


async def get_forecast(
    db: AsyncSession, tenant_id: uuid.UUID, owner_ids: list[uuid.UUID] | None
) -> tuple[dict, str]:
    """Headcount forecast from Phase 4, now also carrying a dollar figure
    (PIPELINE_AND_REVENUE_PLAN.md §5.7) — expected_value extends rather
    than replaces expected_enrollments, so a pre-Phase-6 EdTech tenant
    with deal.value always 0 just sees expected_value stay 0, no
    behavior change."""

    async def compute() -> dict:
        stages = (
            (
                await db.execute(
                    select(PipelineStage)
                    .where(PipelineStage.tenant_id == tenant_id)
                    .order_by(PipelineStage.sort_order)
                )
            )
            .scalars()
            .all()
        )
        count_stmt = select(
            Deal.stage_id, func.count(Deal.id), func.coalesce(func.sum(Deal.value), 0)
        ).where(Deal.tenant_id == tenant_id)
        if owner_ids is not None:
            count_stmt = count_stmt.where(Deal.owner_id.in_(owner_ids))
        rows = (await db.execute(count_stmt.group_by(Deal.stage_id))).all()
        counts = {stage_id: count for stage_id, count, _value in rows}
        values = {stage_id: value for stage_id, _count, value in rows}

        by_stage = []
        total_count = 0.0
        total_value = Decimal("0")
        for stage in stages:
            count = counts.get(stage.id, 0)
            value = values.get(stage.id, Decimal("0"))
            expected_count = count * stage.win_probability_pct / 100
            expected_value = value * stage.win_probability_pct / Decimal("100")
            total_count += expected_count
            total_value += expected_value
            by_stage.append(
                {
                    "stage_id": str(stage.id),
                    "stage_name": stage.name,
                    "deal_count": count,
                    "value": str(value),
                    "win_probability_pct": stage.win_probability_pct,
                    "expected_count": round(expected_count, 2),
                    "expected_value": str(round(expected_value, 2)),
                }
            )
        return {
            "expected_enrollments": round(total_count, 2),
            "expected_value": str(round(total_value, 2)),
            "by_stage": by_stage,
        }

    return await get_or_compute(tenant_id, "forecast", owner_ids, compute)


async def get_sla_compliance(
    db: AsyncSession, tenant_id: uuid.UUID, owner_ids: list[uuid.UUID] | None
) -> tuple[list[dict], str]:
    """Deal-scoped SLA states only (the inner join on Deal naturally
    excludes task-scoped sla_states rows, whose deal_id is NULL) — a
    per-counselor breach/at-risk/on-track breakdown, REQUIREMENTS.md
    §5.2's "SLA compliance view." No trend-over-time (PHASE_4_PLAN.md's
    intro explains why)."""

    async def compute() -> list[dict]:
        stmt = (
            select(Deal.owner_id, SlaState.state, func.count(SlaState.id))
            .select_from(SlaState)
            .join(Deal, (Deal.id == SlaState.deal_id) & (Deal.tenant_id == SlaState.tenant_id))
            .where(SlaState.tenant_id == tenant_id)
        )
        if owner_ids is not None:
            stmt = stmt.where(Deal.owner_id.in_(owner_ids))
        rows = (await db.execute(stmt.group_by(Deal.owner_id, SlaState.state))).all()

        by_counselor: dict[uuid.UUID, dict[str, int]] = {}
        for owner_id, state, count in rows:
            by_counselor.setdefault(owner_id, {"on_track": 0, "at_risk": 0, "breached": 0})[
                state
            ] = count
        if not by_counselor:
            return []

        users = (
            (
                await db.execute(
                    select(User).where(
                        User.tenant_id == tenant_id, User.id.in_(by_counselor.keys())
                    )
                )
            )
            .scalars()
            .all()
        )
        names = {u.id: (u.full_name or u.email) for u in users}

        return [
            {"counselor_id": str(owner_id), "counselor_name": names.get(owner_id), **counts}
            for owner_id, counts in by_counselor.items()
        ]

    return await get_or_compute(tenant_id, "sla_compliance", owner_ids, compute)


async def get_my_queue(
    db: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID
) -> tuple[list[dict], str]:
    async def compute() -> list[dict]:
        rows = (
            await db.execute(
                select(Deal, SlaState.state)
                .outerjoin(
                    SlaState, (SlaState.deal_id == Deal.id) & (SlaState.tenant_id == Deal.tenant_id)
                )
                .where(Deal.tenant_id == tenant_id, Deal.owner_id == user_id)
            )
        ).all()

        deals: dict[uuid.UUID, Deal] = {}
        worst_state: dict[uuid.UUID, str | None] = {}
        for deal, state in rows:
            deals[deal.id] = deal
            current = worst_state.get(deal.id)
            worst_state.setdefault(deal.id, None)
            if state is not None and (
                current is None or _SLA_URGENCY_ORDER[state] < _SLA_URGENCY_ORDER.get(current, 3)
            ):
                worst_state[deal.id] = state

        items = [
            {
                "deal_id": str(deal.id),
                "contact_id": str(deal.contact_id),
                "stage_id": str(deal.stage_id),
                "sla_state": worst_state.get(deal.id),
            }
            for deal in deals.values()
        ]
        items.sort(key=lambda item: _SLA_URGENCY_ORDER.get(item["sla_state"], 3))
        return items

    return await get_or_compute(tenant_id, "my_queue", [user_id], compute)


async def get_invoice_summary(
    db: AsyncSession, tenant_id: uuid.UUID, owner_ids: list[uuid.UUID] | None
) -> tuple[dict, str]:
    """PIPELINE_AND_REVENUE_PLAN.md §5.7 — invoiced/paid/outstanding for
    the current calendar month (by issued_at/paid_at respectively);
    invoice rework rate is all-time (a health metric, not a monthly
    one) — uses invoices.was_reworked (migration 0026, a deviation from
    the original plan — see that migration's own docstring) rather than
    current status, so a reworked-then-resent invoice still counts.
    avg_minutes_in_invoice_stage mirrors app/workers/sla.py's own
    now() - stage_changed_at computation for stage_entry SLA policies,
    for deals *currently* in an is_invoice_stage stage — doesn't include
    duration for invoice stages a deal has already exited, which would
    need per-stage-instance timestamps this schema doesn't track."""

    async def compute() -> dict:
        now = datetime.now(UTC)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        invoiced_stmt = select(func.coalesce(func.sum(Invoice.amount), 0)).where(
            Invoice.tenant_id == tenant_id, Invoice.issued_at >= month_start
        )
        paid_stmt = (
            select(func.coalesce(func.sum(Payment.amount), 0))
            .select_from(Payment)
            .join(
                Invoice,
                (Invoice.id == Payment.invoice_id) & (Invoice.tenant_id == Payment.tenant_id),
            )
            .where(Payment.tenant_id == tenant_id, Payment.paid_at >= month_start)
        )
        rework_stmt = select(
            func.count(Invoice.id),
            func.count(Invoice.id).filter(Invoice.was_reworked.is_(True)),
        ).where(Invoice.tenant_id == tenant_id)
        stage_time_stmt = (
            select(Deal.stage_changed_at)
            .select_from(Deal)
            .join(
                PipelineStage,
                (PipelineStage.id == Deal.stage_id) & (PipelineStage.tenant_id == Deal.tenant_id),
            )
            .where(Deal.tenant_id == tenant_id, PipelineStage.is_invoice_stage.is_(True))
        )
        if owner_ids is not None:
            invoiced_stmt = invoiced_stmt.join(
                Deal, (Deal.id == Invoice.deal_id) & (Deal.tenant_id == Invoice.tenant_id)
            ).where(Deal.owner_id.in_(owner_ids))
            paid_stmt = paid_stmt.join(
                Deal, (Deal.id == Invoice.deal_id) & (Deal.tenant_id == Invoice.tenant_id)
            ).where(Deal.owner_id.in_(owner_ids))
            rework_stmt = rework_stmt.join(
                Deal, (Deal.id == Invoice.deal_id) & (Deal.tenant_id == Invoice.tenant_id)
            ).where(Deal.owner_id.in_(owner_ids))
            stage_time_stmt = stage_time_stmt.where(Deal.owner_id.in_(owner_ids))

        invoiced_total = Decimal((await db.execute(invoiced_stmt)).scalar_one())
        paid_total = Decimal((await db.execute(paid_stmt)).scalar_one())
        total_invoices, reworked_invoices = (await db.execute(rework_stmt)).one()
        rework_rate = round(reworked_invoices / total_invoices, 4) if total_invoices > 0 else 0.0
        stage_changed_ats = (await db.execute(stage_time_stmt)).scalars().all()
        avg_minutes_in_invoice_stage = (
            round(
                sum((now - t).total_seconds() for t in stage_changed_ats)
                / len(stage_changed_ats)
                / 60,
                1,
            )
            if stage_changed_ats
            else None
        )

        return {
            "period": "current_month",
            "invoiced_total": str(invoiced_total),
            "paid_total": str(paid_total),
            "outstanding_total": str(invoiced_total - paid_total),
            "invoice_rework_rate": rework_rate,
            "avg_minutes_in_invoice_stage": avg_minutes_in_invoice_stage,
        }

    return await get_or_compute(tenant_id, "invoice_summary", owner_ids, compute)


async def get_my_stats(
    db: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID
) -> tuple[dict, str]:
    """Leads worked + conversion rate only — response time and demo
    attendance rate need tracking this schema doesn't have yet
    (PHASE_4_PLAN.md's intro)."""

    async def compute() -> dict:
        total = (
            await db.execute(
                select(func.count(Contact.id)).where(
                    Contact.tenant_id == tenant_id, Contact.owner_id == user_id
                )
            )
        ).scalar_one()
        won = (
            await db.execute(
                select(func.count(func.distinct(Deal.id)))
                .select_from(Deal)
                .join(
                    PipelineStage,
                    (PipelineStage.id == Deal.stage_id)
                    & (PipelineStage.tenant_id == Deal.tenant_id),
                )
                .where(
                    Deal.tenant_id == tenant_id,
                    Deal.owner_id == user_id,
                    PipelineStage.is_won.is_(True),
                )
            )
        ).scalar_one()
        conversion_rate = round(won / total, 4) if total > 0 else 0.0
        return {"leads_worked": total, "won_count": won, "conversion_rate": conversion_rate}

    return await get_or_compute(tenant_id, "my_stats", [user_id], compute)
