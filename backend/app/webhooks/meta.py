"""Meta Lead Ads webhook — bypasses the BFF entirely (CLAUDE.md rule 4 is
about the browser session; this is a server-to-server callback from
Meta, not a browser request), registered directly on `backend` outside
/api/v1 (PHASE_2_PLAN.md §4.2).

Flow: verify X-Hub-Signature-256 -> extract page_id (the account this
webhook came from) + leadgen_id -> resolve_connection (the one place a
tenant_id gets discovered from an external id, PHASE_2_PLAN.md §3) ->
fetch full lead field_data from the Graph API (mocked in dev via
META_GRAPH_API_BASE_URL) -> normalize via the existing MetaConnector
(same normalize() the dev-seed path already exercises and
test_connectors_normalize.py already tests) -> ingest.

Always returns 200 once the signature is valid, even for a benign skip
(unknown account, already-ingested event) — Meta redelivers on non-2xx,
and skip reasons here are never worth a redelivery storm. Only a bad
signature or malformed payload gets a non-2xx.
"""

import json

import httpx
from fastapi import APIRouter, Request, Response

from app.connectors.meta import MetaConnector
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


@router.get("/webhooks/meta")
async def verify_meta_subscription(request: Request) -> Response:
    """Meta's subscription verification handshake — echoes hub.challenge
    back only if hub.verify_token matches ours."""
    settings = get_settings()
    if (
        request.query_params.get("hub.mode") == "subscribe"
        and request.query_params.get("hub.verify_token") == settings.meta_webhook_verify_token
    ):
        challenge = request.query_params.get("hub.challenge", "")
        return Response(content=challenge, media_type="text/plain")
    return Response(status_code=403)


@router.post("/webhooks/meta")
async def receive_meta_webhook(request: Request) -> dict:
    settings = get_settings()
    raw_body = await request.body()

    if not verify_meta_signature(
        raw_body, request.headers.get("x-hub-signature-256"), settings.meta_app_secret
    ):
        raise ApiError(401, UNAUTHORIZED, "Invalid webhook signature")

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise ApiError(400, VALIDATION_ERROR, "Malformed webhook payload") from exc

    sessionmaker = get_sessionmaker()
    async with httpx.AsyncClient(base_url=settings.meta_graph_api_base_url) as graph_client:
        for entry in payload.get("entry", []):
            page_id = entry.get("id")
            for change in entry.get("changes", []):
                if change.get("field") != "leadgen":
                    continue
                leadgen_id = change.get("value", {}).get("leadgen_id")
                if not page_id or not leadgen_id:
                    continue

                async with sessionmaker() as db:
                    connection = await resolve_connection(db, "meta", page_id)
                if connection is None:
                    logger.info("meta_webhook_unknown_account")
                    continue

                response = await graph_client.get(f"/v18.0/{leadgen_id}")
                response.raise_for_status()
                lead = MetaConnector().normalize(response.json())
                await ingest_lead(connection.tenant_id, "meta", lead)

    return data_envelope({"status": "received"}, request.state.request_id)
