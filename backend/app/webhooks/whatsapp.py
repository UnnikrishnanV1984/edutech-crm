"""WhatsApp Cloud API webhook — same HMAC verification mechanism as Meta
Lead Ads (both are Meta platforms), separate app secret
(PHASE_2_PLAN.md §3). Scope is lead ingestion only (inbound message ->
new contact), not the full "templates, reminders, 2-way chat" WhatsApp
integration filed under FEATURES_AND_PLAN.md Phase 3 — no outbound
sending here.

The full message content (not just an id to fetch, unlike Meta Lead
Ads) arrives in the webhook body itself, so there's no follow-up API
call. Course interest, when present, comes from an interactive list
reply (a WhatsApp catalog-style "which course?" prompt) — its
list_reply.id is treated as the course code, reshaped into the same
dict shape WhatsAppConnector.normalize() already parses so the mapping
logic isn't duplicated.
"""

import json

from fastapi import APIRouter, Request, Response

from app.connectors.whatsapp import WhatsAppConnector
from app.core.config import get_settings
from app.core.envelope import data_envelope
from app.core.errors import UNAUTHORIZED, VALIDATION_ERROR, ApiError
from app.core.logging import get_logger
from app.db.session import get_sessionmaker
from app.services.lead_ingestion_service import ingest_lead
from app.services.lead_source_connection_service import resolve_connection
from app.webhooks.signature import verify_meta_signature

router = APIRouter(tags=["webhooks"])
logger = get_logger(__name__)


@router.get("/webhooks/whatsapp")
async def verify_whatsapp_subscription(request: Request) -> Response:
    settings = get_settings()
    if (
        request.query_params.get("hub.mode") == "subscribe"
        and request.query_params.get("hub.verify_token")
        == settings.whatsapp_webhook_verify_token
    ):
        challenge = request.query_params.get("hub.challenge", "")
        return Response(content=challenge, media_type="text/plain")
    return Response(status_code=403)


def _extract_course_code(message: dict) -> str | None:
    if message.get("type") != "interactive":
        return None
    return message.get("interactive", {}).get("list_reply", {}).get("id")


@router.post("/webhooks/whatsapp")
async def receive_whatsapp_webhook(request: Request) -> dict:
    settings = get_settings()
    raw_body = await request.body()

    if not verify_meta_signature(
        raw_body, request.headers.get("x-hub-signature-256"), settings.whatsapp_app_secret
    ):
        raise ApiError(401, UNAUTHORIZED, "Invalid webhook signature")

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise ApiError(400, VALIDATION_ERROR, "Malformed webhook payload") from exc

    sessionmaker = get_sessionmaker()
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") != "messages":
                continue
            value = change.get("value", {})
            phone_number_id = value.get("metadata", {}).get("phone_number_id")
            messages = value.get("messages", [])
            contacts = value.get("contacts", [])
            if not phone_number_id or not messages or not contacts:
                continue

            async with sessionmaker() as db:
                connection = await resolve_connection(db, "whatsapp", phone_number_id)
            if connection is None:
                logger.info("whatsapp_webhook_unknown_account")
                continue

            message = messages[0]
            record = {
                "message_id": message["id"],
                "timestamp": message["timestamp"],
                "contact": contacts[0],
                "context": {"course_code": _extract_course_code(message)},
            }
            lead = WhatsAppConnector().normalize(record)
            await ingest_lead(connection.tenant_id, "whatsapp", lead)

    return data_envelope({"status": "received"}, request.state.request_id)
