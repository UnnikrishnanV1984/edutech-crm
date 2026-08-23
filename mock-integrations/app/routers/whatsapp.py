"""Stands in for WhatsApp Cloud API webhook delivery — PHASE_2_PLAN.md
§4.4. Unlike Meta Lead Ads, the full message content arrives in the
webhook body itself (WhatsApp has no separate fetch step), so GET here
exists only for parity/testability, not because backend calls it.
"""

import json
import time
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import get_settings
from app.signature import sign

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])

_FIXTURES = json.loads((Path(__file__).parent.parent / "fixtures" / "whatsapp.json").read_text())


def _message_id(record: dict) -> str:
    return f"wamid.mock-{record['wa_id']}"


@router.get("/v18.0/{message_id}")
async def get_message(message_id: str) -> dict:
    record = next((r for r in _FIXTURES if _message_id(r) == message_id), None)
    if record is None:
        raise HTTPException(status_code=404, detail="Unknown message_id")
    return record


class TriggerRequest(BaseModel):
    external_account_id: str
    wa_id: str | None = None


@router.post("/_trigger")
async def trigger_webhook(body: TriggerRequest) -> dict:
    record = (
        next((r for r in _FIXTURES if r["wa_id"] == body.wa_id), None)
        if body.wa_id
        else _FIXTURES[0]
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Unknown wa_id")

    message: dict = {
        "id": _message_id(record),
        "timestamp": str(int(time.time())),
    }
    if record["course_code"]:
        message["type"] = "interactive"
        message["interactive"] = {
            "type": "list_reply",
            "list_reply": {"id": record["course_code"], "title": record["course_code"]},
        }
    else:
        message["type"] = "text"
        message["text"] = {"body": "Hi, I'd like more information."}

    contact = {"profile": {"name": record["name"]}, "wa_id": record["wa_id"]}
    envelope = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "mock-waba-id",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "metadata": {"phone_number_id": body.external_account_id},
                            "contacts": [contact],
                            "messages": [message],
                        },
                    }
                ],
            }
        ],
    }
    raw_body = json.dumps(envelope).encode("utf-8")
    settings = get_settings()
    signature = sign(raw_body, settings.whatsapp_app_secret)

    async with httpx.AsyncClient(base_url=settings.backend_base_url) as client:
        response = await client.post(
            "/webhooks/whatsapp",
            content=raw_body,
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": signature},
        )
    return {"message_id": message["id"], "backend_status": response.status_code}
