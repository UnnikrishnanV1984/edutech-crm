"""Escalation snooze expiry — OPENFUNNEL_REBRAND_PLAN.md Phase 7e. Runs on
a 5-minute Celery Beat schedule (celery_app.py), same
dispatch-one-task-per-tenant shape as app/workers/sla.py, so one tenant's
volume can't block another's.

Uses the DB server's own now() for the `snoozed_until <=` comparison, not
the app process's clock — the same clock-skew class of bug
app/services/report_service.py's resolve_period already had to fix twice
(Docker Desktop's VM clock can drift ahead of the app process's).
"""

import asyncio
import uuid

from sqlalchemy import select, text

from app.core.logging import get_logger
from app.db.session import get_sessionmaker
from app.models.tenant import Tenant
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


async def _set_tenant(db, tenant_id: uuid.UUID) -> None:
    await db.execute(
        text("SELECT set_config('app.tenant_id', :tenant_id, true)"), {"tenant_id": str(tenant_id)}
    )


@celery_app.task(name="app.workers.escalations.expire_snoozed_escalations")
def expire_snoozed_escalations(tenant_id: str) -> None:
    asyncio.run(_expire_snoozed_escalations(uuid.UUID(tenant_id)))


async def _expire_snoozed_escalations(tenant_id: uuid.UUID) -> None:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as db, db.begin():
        await _set_tenant(db, tenant_id)
        result = await db.execute(
            text(
                "UPDATE escalations SET status = 'open', snoozed_until = NULL "
                "WHERE tenant_id = :tenant_id AND status = 'snoozed' "
                "AND snoozed_until <= now()"
            ),
            {"tenant_id": str(tenant_id)},
        )
        if result.rowcount:
            logger.info(
                "escalations_unsnoozed", tenant_id=str(tenant_id), count=result.rowcount
            )


@celery_app.task(name="app.workers.escalations.dispatch_snooze_expiry_scan")
def dispatch_snooze_expiry_scan() -> None:
    asyncio.run(_dispatch_snooze_expiry_scan())


async def _dispatch_snooze_expiry_scan() -> None:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as db:
        result = await db.execute(select(Tenant.id).where(Tenant.status == "active"))
        tenant_ids = list(result.scalars().all())
    for tenant_id in tenant_ids:
        expire_snoozed_escalations.delay(str(tenant_id))
