from datetime import UTC, datetime
from typing import Any

from app.connectors.base import RawLead, SeedFileConnector


class WhatsAppConnector(SeedFileConnector):
    """WhatsApp Business API-shaped: a message payload keyed by `wa_id`
    (E.164 without the leading '+', as WhatsApp actually sends it) with no
    email — realistic for this channel, and exercises contacts.email's
    nullable dedupe path. A real integration would override
    fetch_raw_leads to read from the WhatsApp webhook instead —
    normalize() stays the same."""

    source = "whatsapp"
    seed_filename = "whatsapp.json"

    def normalize(self, record: dict[str, Any]) -> RawLead:
        return RawLead(
            external_id=record["message_id"],
            full_name=record["contact"]["profile"]["name"],
            email=None,
            phone=f"+{record['contact']['wa_id']}",
            course_code=record.get("context", {}).get("course_code"),
            occurred_at=datetime.fromtimestamp(int(record["timestamp"]), tz=UTC),
            raw=record,
        )
