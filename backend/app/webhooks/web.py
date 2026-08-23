"""Embeddable web-form lead capture — the one fully public, unauthenticated,
unsigned lead-capture route (there's no platform secret to verify
against; the "credential" is the embed key itself,
PHASE_2_PLAN.md §3/§6 step 15). Rate limited per embed key since it has
no signature check to reject abuse before doing work."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Request

from app.connectors.base import RawLead
from app.core.config import get_settings
from app.core.envelope import data_envelope
from app.core.errors import NOT_FOUND, ApiError
from app.core.rate_limit import enforce_rate_limit
from app.db.session import get_sessionmaker
from app.schemas.webhook import WebLeadCreate
from app.services.lead_ingestion_service import ingest_lead
from app.services.lead_source_connection_service import resolve_connection

router = APIRouter(tags=["webhooks"])


@router.post("/webhooks/web")
async def receive_web_lead(request: Request, body: WebLeadCreate) -> dict:
    async with get_sessionmaker()() as db:
        connection = await resolve_connection(db, "web", body.embed_key)
    if connection is None:
        raise ApiError(404, NOT_FOUND, "Unknown form")

    await enforce_rate_limit(
        f"web:{body.embed_key}", get_settings().web_form_rate_limit_per_minute
    )

    lead = RawLead(
        external_id=body.idempotency_key or str(uuid.uuid4()),
        full_name=body.full_name,
        email=body.email,
        phone=body.phone,
        course_code=body.course_code,
        occurred_at=datetime.now(UTC),
        raw=body.model_dump(),
    )
    await ingest_lead(connection.tenant_id, "web", lead)

    return data_envelope({"status": "received"}, request.state.request_id)
