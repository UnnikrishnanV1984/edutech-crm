"""Outbound Meta/Google conversion signals — ARCHITECTURE.md §7d,
PHASE_4B_CONVERSIONS_PLAN.md §5.2. Enqueued by the deal stage-change
route (app/api/deals.py) right after that transaction commits, once per
platform, whenever a deal enters an is_won pipeline stage.

Mirrors app/workers/rules.py's _run_one_rule structure deliberately: its
own short transaction per attempt, a local retry loop (not Celery's
task-level retry), and a fresh transaction to record final failure
after retries are exhausted — same "one bad attempt can't poison a
later one" reasoning.

conversion_events is one row per (tenant_id, deal_id, platform) — unlike
workflow_runs' insert-many-rows-per-source pattern, every write here is
an upsert against that one row, which is also what makes a duplicate
enqueue for an already-'sent' pair a no-op (_already_sent short-circuits
before any write).
"""

import asyncio
import hashlib
import uuid
from datetime import UTC, datetime

import httpx
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import get_settings
from app.core.crypto import decrypt_token
from app.core.logging import get_logger
from app.db.session import get_sessionmaker
from app.models.contact import Contact
from app.models.conversion_event import ConversionEvent
from app.models.deal import Deal
from app.services.contact_service import get_contact
from app.services.deal_service import get_deal
from app.services.lead_source_connection_service import get_active_connection
from app.workers.celery_app import celery_app

logger = get_logger(__name__)

_MAX_ATTEMPTS = 3


async def _set_tenant(db, tenant_id: uuid.UUID) -> None:
    await db.execute(
        text("SELECT set_config('app.tenant_id', :tenant_id, true)"), {"tenant_id": str(tenant_id)}
    )


def _hash(value: str) -> str:
    # Meta's real Conversions API requires user_data fields to be
    # SHA-256 hashed (lowercased, trimmed) — matching that here means
    # swapping META_GRAPH_API_BASE_URL to the real platform later needs
    # no payload-shape change, same config-swap-only principle as §7b.
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()


async def _already_sent(db, tenant_id: uuid.UUID, deal_id: uuid.UUID, platform: str) -> bool:
    result = await db.execute(
        select(ConversionEvent.id).where(
            ConversionEvent.tenant_id == tenant_id,
            ConversionEvent.deal_id == deal_id,
            ConversionEvent.platform == platform,
            ConversionEvent.status == "sent",
        )
    )
    return result.scalar_one_or_none() is not None


async def _record_event(
    db,
    tenant_id: uuid.UUID,
    deal_id: uuid.UUID,
    platform: str,
    status: str,
    attempts: int,
    error_message: str | None = None,
    sent_at: datetime | None = None,
) -> None:
    stmt = pg_insert(ConversionEvent).values(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        deal_id=deal_id,
        platform=platform,
        status=status,
        attempts=attempts,
        last_error=error_message,
        sent_at=sent_at,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[
            ConversionEvent.tenant_id,
            ConversionEvent.deal_id,
            ConversionEvent.platform,
        ],
        set_={
            "status": stmt.excluded.status,
            "attempts": stmt.excluded.attempts,
            "last_error": stmt.excluded.last_error,
            "sent_at": stmt.excluded.sent_at,
            "updated_at": func.now(),
        },
    )
    await db.execute(stmt)
    await db.flush()


async def _call_meta(target_id: str, access_token: str, deal: Deal, contact: Contact) -> None:
    settings = get_settings()
    async with httpx.AsyncClient(base_url=settings.meta_graph_api_base_url) as client:
        response = await client.post(
            f"/v18.0/{target_id}/events",
            params={"access_token": access_token},
            json={
                "data": [
                    {
                        "event_name": "Enrolled",
                        "event_time": int(deal.stage_changed_at.timestamp()),
                        "action_source": "system_generated",
                        "user_data": {
                            "em": [_hash(contact.email)] if contact.email else [],
                            "ph": [_hash(contact.phone)] if contact.phone else [],
                        },
                    }
                ]
            },
        )
        response.raise_for_status()


async def _call_google(
    target_id: str, access_token: str, external_account_id: str, deal: Deal, contact: Contact
) -> None:
    settings = get_settings()
    async with httpx.AsyncClient(base_url=settings.google_ads_api_base_url) as client:
        response = await client.post(
            f"/customers/{external_account_id}/conversions",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "conversion_action": target_id,
                "conversion_date_time": deal.stage_changed_at.isoformat(),
                "user_identifiers": {
                    "hashed_email": _hash(contact.email) if contact.email else None,
                    "hashed_phone_number": _hash(contact.phone) if contact.phone else None,
                },
            },
        )
        response.raise_for_status()


@celery_app.task(name="app.workers.conversions.send_conversion_event")
def send_conversion_event(tenant_id: str, deal_id: str, platform: str) -> None:
    asyncio.run(_send_conversion_event(uuid.UUID(tenant_id), uuid.UUID(deal_id), platform))


async def _send_conversion_event(tenant_id: uuid.UUID, deal_id: uuid.UUID, platform: str) -> None:
    """One (deal, platform) pair, its own session/transaction per
    attempt, up to _MAX_ATTEMPTS local retries — mirrors
    app/workers/rules.py's _run_one_rule."""
    sessionmaker = get_sessionmaker()
    last_error: str | None = None

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            async with sessionmaker() as db, db.begin():
                await _set_tenant(db, tenant_id)

                if await _already_sent(db, tenant_id, deal_id, platform):
                    return

                connection = await get_active_connection(db, tenant_id, platform)
                if connection is None or not connection.conversion_target_id:
                    # Static missing-config state — retrying won't help,
                    # so record and return rather than looping 3 times.
                    await _record_event(
                        db,
                        tenant_id,
                        deal_id,
                        platform,
                        "failed",
                        attempt,
                        "no active connection configured",
                    )
                    return

                deal = await get_deal(db, tenant_id, deal_id)
                if deal is None:
                    await _record_event(
                        db, tenant_id, deal_id, platform, "failed", attempt, "deal not found"
                    )
                    return
                contact = await get_contact(db, tenant_id, deal.contact_id)
                if contact is None:
                    await _record_event(
                        db, tenant_id, deal_id, platform, "failed", attempt, "contact not found"
                    )
                    return

                access_token = await decrypt_token(db, connection.access_token_encrypted)
                if platform == "meta":
                    await _call_meta(connection.conversion_target_id, access_token, deal, contact)
                else:
                    await _call_google(
                        connection.conversion_target_id,
                        access_token,
                        connection.external_account_id,
                        deal,
                        contact,
                    )

                await _record_event(
                    db, tenant_id, deal_id, platform, "sent", attempt, sent_at=datetime.now(UTC)
                )
            return  # committed successfully
        except Exception as exc:  # noqa: BLE001 — any platform call can raise
            last_error = str(exc)
            logger.warning(
                "conversion_send_attempt_failed",
                tenant_id=str(tenant_id),
                deal_id=str(deal_id),
                platform=platform,
                attempt=attempt,
                error=last_error,
            )

    # Exhausted retries — record exactly one failure in a fresh
    # transaction, matching rules.py's tail (whatever the last attempt
    # touched may be in a rolled-back, unusable state).
    async with sessionmaker() as db, db.begin():
        await _set_tenant(db, tenant_id)
        await _record_event(db, tenant_id, deal_id, platform, "failed", _MAX_ATTEMPTS, last_error)
