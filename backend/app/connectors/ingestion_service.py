"""Runs every lead connector for one tenant, writing through the exact
same service-layer functions a real HTTP request uses — no shortcut
write path (SEED_CONNECTORS_PLAN.md). Each unit of work (course seeding,
each lead) is its own short transaction with its own
set_config('app.tenant_id', ...), mirroring how a real request-scoped
transaction behaves, so one bad lead can't poison an entire tenant's run.
"""

import asyncio
import json
import logging
import sys
import uuid

from sqlalchemy import text

from app.connectors.base import SEED_DATA_DIR, LeadConnector, RawLead
from app.connectors.google import GoogleConnector
from app.connectors.meta import MetaConnector
from app.connectors.web import WebConnector
from app.connectors.whatsapp import WhatsAppConnector
from app.core.errors import ApiError
from app.core.redis import get_redis_client
from app.db.session import get_sessionmaker
from app.schemas.contact import ContactCreate
from app.schemas.course import CourseCreate
from app.schemas.deal import DealCreate
from app.services import activity_service, contact_service, course_service, deal_service
from app.services.user_service import list_counselor_ids

logger = logging.getLogger(__name__)

if sys.platform == "win32":
    # Same constraint as app/main.py and app/db/seed.py — this module is
    # used both by the standalone seed_runner.py entrypoint and directly
    # by tests, so it needs the guard independently of either caller.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

CONNECTORS: list[type[LeadConnector]] = [
    MetaConnector,
    GoogleConnector,
    WebConnector,
    WhatsAppConnector,
]


async def _set_tenant(db, tenant_id: uuid.UUID) -> None:
    await db.execute(
        text("SELECT set_config('app.tenant_id', :tenant_id, true)"), {"tenant_id": str(tenant_id)}
    )


async def seed_courses(db, tenant_id: uuid.UUID) -> dict[str, uuid.UUID]:
    """Idempotent by (tenant_id, code) — same proactive-check-then-create
    pattern contact dedupe uses. Returns a code -> course_id map for
    resolving each lead's course_code."""
    with (SEED_DATA_DIR / "courses.json").open(encoding="utf-8") as f:
        records = json.load(f)

    course_ids: dict[str, uuid.UUID] = {}
    for record in records:
        existing = await course_service.get_course_by_code(db, tenant_id, record["code"])
        if existing is not None:
            course_ids[record["code"]] = existing.id
            continue
        course = await course_service.create_course(
            db, tenant_id, CourseCreate(name=record["name"], code=record["code"])
        )
        course_ids[record["code"]] = course.id
    return course_ids


async def _setup(tenant_id: uuid.UUID) -> tuple[list[uuid.UUID], dict[str, uuid.UUID]]:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as db, db.begin():
        await _set_tenant(db, tenant_id)
        counselor_ids = await list_counselor_ids(db, tenant_id)
        course_ids = await seed_courses(db, tenant_id)
    return counselor_ids, course_ids


async def _ingest_one_lead(
    tenant_id: uuid.UUID, source: str, lead: RawLead, course_id: uuid.UUID, owner_id: uuid.UUID
) -> bool:
    """Returns True if a new contact/deal/activity was created, False if
    a dedupe conflict means this lead was already ingested (or
    coincidentally matches an existing contact) — either way the caller
    still marks the Redis idempotency key."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as db, db.begin():
        await _set_tenant(db, tenant_id)
        try:
            contact = await contact_service.create_contact(
                db,
                tenant_id,
                ContactCreate(
                    full_name=lead.full_name,
                    email=lead.email,
                    phone=lead.phone,
                    lead_source=source,
                ),
                default_owner_id=owner_id,
            )
        except ApiError:
            return False

        deal = await deal_service.create_deal(
            db, tenant_id, contact.id, DealCreate(course_id=course_id), default_owner_id=owner_id
        )
        await activity_service.log_lead_captured(
            db,
            tenant_id,
            contact_id=contact.id,
            deal_id=deal.id,
            actor_id=owner_id,
            source=source,
            external_id=lead.external_id,
        )
    return True


async def ingest_all(tenant_id: uuid.UUID) -> int:
    """Runs every connector for one tenant. Returns the count of leads
    actually created (excludes ones already marked ingested in Redis, or
    a course_code with no matching seeded course)."""
    counselor_ids, course_ids = await _setup(tenant_id)
    if not counselor_ids:
        logger.warning("seed_ingestion_skipped_no_counselors tenant_id=%s", tenant_id)
        return 0

    redis = get_redis_client()
    ingested = 0
    owner_index = 0

    try:
        for connector_cls in CONNECTORS:
            connector = connector_cls()
            for lead in connector.fetch_raw_leads():
                redis_key = f"seed:ingested:{tenant_id}:{connector.source}:{lead.external_id}"
                if await redis.exists(redis_key):
                    continue

                course_id = course_ids.get(lead.course_code)
                if course_id is None:
                    logger.warning(
                        "seed_ingestion_skipped_unknown_course tenant_id=%s course_code=%s",
                        tenant_id,
                        lead.course_code,
                    )
                    continue

                owner_id = counselor_ids[owner_index % len(counselor_ids)]
                owner_index += 1

                created = await _ingest_one_lead(
                    tenant_id, connector.source, lead, course_id, owner_id
                )
                await redis.set(redis_key, "1")
                if created:
                    ingested += 1
    finally:
        await redis.aclose()

    return ingested
