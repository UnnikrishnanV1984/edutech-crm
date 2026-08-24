"""Stands in for the Meta Graph API (leadgen fetch) and for Meta itself
delivering a webhook — PHASE_2_PLAN.md §4.4. `external_account_id` in
_trigger's body is the caller's choice (the page_id of whichever
lead_source_connections row they're simulating traffic for) — the mock
has no idea which tenant that maps to, and doesn't need to; that
resolution happens on backend's side.
"""

import json
import time
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import get_settings
from app.signature import sign

router = APIRouter(prefix="/meta", tags=["meta"])

_FIXTURES = json.loads((Path(__file__).parent.parent / "fixtures" / "meta.json").read_text())


@router.get("/v18.0/{leadgen_id}")
async def get_leadgen(leadgen_id: str) -> dict:
    record = next((r for r in _FIXTURES if r["id"] == leadgen_id), None)
    if record is None:
        raise HTTPException(status_code=404, detail="Unknown leadgen_id")
    return record


class TriggerRequest(BaseModel):
    external_account_id: str
    leadgen_id: str | None = None


@router.post("/v18.0/{pixel_id}/events")
async def receive_conversion_events(pixel_id: str, body: dict) -> dict:
    """Stands in for the real Meta Conversions API — ARCHITECTURE.md
    §7d. No real validation of access_token or user_data hashing; this
    only needs to accept the shape backend actually sends and report how
    many events it got, matching this router's existing leniency for
    _trigger below."""
    events = body.get("data", [])
    return {"events_received": len(events)}


@router.post("/_trigger")
async def trigger_webhook(body: TriggerRequest) -> dict:
    record = (
        next((r for r in _FIXTURES if r["id"] == body.leadgen_id), None)
        if body.leadgen_id
        else _FIXTURES[0]
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Unknown leadgen_id")

    envelope = {
        "object": "page",
        "entry": [
            {
                "id": body.external_account_id,
                "time": int(time.time()),
                "changes": [
                    {
                        "field": "leadgen",
                        "value": {
                            "leadgen_id": record["id"],
                            "page_id": body.external_account_id,
                            "form_id": record["form_id"],
                            "ad_id": record["ad_id"],
                            "created_time": record["created_time"],
                        },
                    }
                ],
            }
        ],
    }
    raw_body = json.dumps(envelope).encode("utf-8")
    settings = get_settings()
    signature = sign(raw_body, settings.meta_app_secret)

    async with httpx.AsyncClient(base_url=settings.backend_base_url) as client:
        response = await client.post(
            "/webhooks/meta",
            content=raw_body,
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": signature},
        )
    return {"leadgen_id": record["id"], "backend_status": response.status_code}
