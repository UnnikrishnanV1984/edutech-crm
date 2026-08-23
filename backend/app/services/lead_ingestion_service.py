"""Shared ingestion path for a single already-tenant-resolved lead,
called from app/webhooks/{meta,whatsapp,web}.py and
app/services/google_sync_service.py. Deliberately separate from
app/connectors/ingestion_service.py (the dev-seed batch path): that one
runs at container boot with no HTTP caller and its own "seed:ingested:"
Redis prefix; this one runs per inbound webhook/pull event with the
"webhook:ingested:" prefix API_CONVENTIONS.md §7 specifies, and fails
closed on Redis unavailability (raises rather than swallowing, so the
caller returns 5xx and the platform redelivers — PHASE_2_PLAN.md §3)
instead of skipping the dedupe check.

Each lead gets its own short transaction with its own
set_config('app.tenant_id', ...), mirroring the same per-unit-of-work
pattern ingestion_service.py established — this runs outside any
FastAPI-request-scoped transaction, since a webhook has no tenant
context (and therefore no get_tenant_context-provided session) until
resolve_connection has already run.
"""

import uuid

from sqlalchemy import text

from app.connectors.base import RawLead
from app.core.errors import ApiError
from app.core.logging import get_logger
from app.core.redis import get_redis_client
from app.db.session import get_sessionmaker
from app.schemas.contact import ContactCreate
from app.schemas.deal import DealCreate
from app.services import activity_service, contact_service, course_service, deal_service
from app.services.user_service import list_counselor_ids

logger = get_logger(__name__)

IDEMPOTENCY_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days — API_CONVENTIONS.md §7 / PHASE_2_PLAN.md §3


async def _set_tenant(db, tenant_id: uuid.UUID) -> None:
    await db.execute(
        text("SELECT set_config('app.tenant_id', :tenant_id, true)"), {"tenant_id": str(tenant_id)}
    )


async def ingest_lead(tenant_id: uuid.UUID, source: str, lead: RawLead) -> bool:
    """Returns True if a new contact was created, False if this event was
    already ingested, a dedupe conflict matched an existing contact, or
    the tenant has no counselor to assign as owner. Redis/DB errors
    propagate rather than being caught — the caller (a webhook route)
    must fail closed (5xx) rather than silently drop a lead."""
    redis = get_redis_client()
    try:
        idempotency_key = f"webhook:ingested:{tenant_id}:{source}:{lead.external_id}"
        if await redis.exists(idempotency_key):
            return False

        sessionmaker = get_sessionmaker()
        async with sessionmaker() as db, db.begin():
            await _set_tenant(db, tenant_id)

            counselor_ids = await list_counselor_ids(db, tenant_id)
            if not counselor_ids:
                logger.warning(
                    "lead_ingestion_skipped_no_counselors", tenant_id=str(tenant_id), source=source
                )
                return False

            # Redis INCR gives a stateless round-robin cursor shared across
            # every inbound lead for this tenant — unlike
            # ingestion_service.py's batch run, a webhook has no in-process
            # loop variable to carry the cursor between calls.
            owner_index = await redis.incr(f"roundrobin:{tenant_id}:owner")
            owner_id = counselor_ids[(owner_index - 1) % len(counselor_ids)]

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
                # Dedupe conflict — same outcome as an already-ingested
                # event, so still mark the idempotency key below.
                await redis.set(idempotency_key, "1", ex=IDEMPOTENCY_TTL_SECONDS)
                return False

            deal_id = None
            course = None
            if lead.course_code:
                course = await course_service.get_course_by_code(db, tenant_id, lead.course_code)
            if course is None:
                logger.warning(
                    "lead_ingestion_no_course_match",
                    tenant_id=str(tenant_id),
                    source=source,
                    course_code=lead.course_code,
                )
            else:
                deal = await deal_service.create_deal(
                    db,
                    tenant_id,
                    contact.id,
                    DealCreate(course_id=course.id),
                    default_owner_id=owner_id,
                )
                deal_id = deal.id

            await activity_service.log_lead_captured(
                db,
                tenant_id,
                contact_id=contact.id,
                deal_id=deal_id,
                actor_id=owner_id,
                source=source,
                external_id=lead.external_id,
            )

        await redis.set(idempotency_key, "1", ex=IDEMPOTENCY_TTL_SECONDS)
        return True
    finally:
        await redis.aclose()
