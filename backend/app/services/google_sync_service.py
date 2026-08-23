"""Google Ads Lead Form pull sync — no inbound webhook (Google's real
mechanism is a pull backend initiates itself). No Celery/BullMQ worker
infrastructure exists yet in this repo (ARCHITECTURE.md doesn't list one
until Phase 3), so this runs admin-triggered via
POST /api/v1/lead-source-connections/{id}/sync rather than on a
scheduler — an explicit boundary, not a silent gap (PHASE_2_PLAN.md
§4.3). Automatic periodic polling is a follow-up once background-job
infrastructure exists.
"""

import uuid
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.google import GoogleConnector
from app.core.config import get_settings
from app.core.crypto import decrypt_token, encrypt_token
from app.core.errors import CONFLICT, ApiError
from app.models.lead_source_connection import LeadSourceConnection
from app.services.lead_ingestion_service import ingest_lead


async def _ensure_valid_access_token(db: AsyncSession, connection: LeadSourceConnection) -> str:
    now = datetime.now(UTC)
    if connection.access_token_encrypted and (
        connection.token_expires_at is None or connection.token_expires_at > now
    ):
        return await decrypt_token(db, connection.access_token_encrypted)

    if not connection.refresh_token_encrypted:
        raise ApiError(
            409, CONFLICT, "Connection has no refresh token on file — reconnect required"
        )
    refresh_token = await decrypt_token(db, connection.refresh_token_encrypted)

    settings = get_settings()
    async with httpx.AsyncClient(base_url=settings.google_ads_api_base_url) as client:
        response = await client.post(
            "/oauth/token",
            json={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": settings.google_oauth_client_id,
                "client_secret": settings.google_oauth_client_secret,
            },
        )
        response.raise_for_status()
    token_data = response.json()

    connection.access_token_encrypted = await encrypt_token(db, token_data["access_token"])
    connection.token_expires_at = now + timedelta(seconds=token_data.get("expires_in", 3600))
    await db.flush()
    return token_data["access_token"]


async def sync_connection(
    db: AsyncSession, tenant_id: uuid.UUID, connection: LeadSourceConnection
) -> int:
    """Returns the count of leads actually created (excludes ones already
    ingested per app/services/lead_ingestion_service.py's idempotency
    check)."""
    settings = get_settings()
    access_token = await _ensure_valid_access_token(db, connection)

    async with httpx.AsyncClient(base_url=settings.google_ads_api_base_url) as client:
        response = await client.get(
            f"/customers/{connection.external_account_id}/leads",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
    records = response.json()

    ingested = 0
    for record in records:
        lead = GoogleConnector().normalize(record)
        if await ingest_lead(tenant_id, "google", lead):
            ingested += 1

    connection.last_synced_at = datetime.now(UTC)
    await db.flush()
    return ingested
