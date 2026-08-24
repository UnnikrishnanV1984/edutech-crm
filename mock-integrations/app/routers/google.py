"""Stands in for Google's OAuth token endpoint and the Ads leads pull —
PHASE_2_PLAN.md §4.4. No real validation of client_id/secret/refresh
token values (there's nothing real to validate against), but it does
require the shapes backend actually sends, so a wiring bug on backend's
side still surfaces as a real HTTP error rather than silently working.
"""

import json
import uuid
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException

router = APIRouter(prefix="/google", tags=["google"])

_FIXTURES = json.loads((Path(__file__).parent.parent / "fixtures" / "google.json").read_text())


@router.post("/oauth/token")
async def token_exchange(body: dict) -> dict:
    if not body.get("refresh_token") and body.get("grant_type") != "authorization_code":
        raise HTTPException(status_code=400, detail="Missing refresh_token")
    return {
        "access_token": f"mock-access-{uuid.uuid4()}",
        "refresh_token": body.get("refresh_token") or f"mock-refresh-{uuid.uuid4()}",
        "expires_in": 3600,
    }


@router.get("/customers/{customer_id}/leads")
async def list_leads(customer_id: str, authorization: str | None = Header(default=None)) -> list:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return _FIXTURES


@router.post("/customers/{customer_id}/conversions")
async def receive_conversion(
    customer_id: str, body: dict, authorization: str | None = Header(default=None)
) -> dict:
    """Stands in for the real Google Ads offline-conversions upload
    endpoint — ARCHITECTURE.md §7d. Simplified path, matching this
    router's existing /leads route rather than the real API's much more
    verbose REST shape (customers/{id}:uploadClickConversions)."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    if not body.get("conversion_action"):
        raise HTTPException(status_code=400, detail="Missing conversion_action")
    return {"results": [{"conversion_action": body["conversion_action"]}]}
