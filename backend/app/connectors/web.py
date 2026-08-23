from datetime import datetime
from typing import Any

from app.connectors.base import RawLead, SeedFileConnector


class WebConnector(SeedFileConnector):
    """Our own embeddable lead-capture form's submission shape
    (FEATURES_AND_PLAN.md's "Web form / landing page lead capture"). A
    real integration would override fetch_raw_leads to read from that
    endpoint's own storage instead — normalize() stays the same."""

    source = "web"
    seed_filename = "web.json"

    def normalize(self, record: dict[str, Any]) -> RawLead:
        return RawLead(
            external_id=record["submission_id"],
            full_name=record["name"],
            email=record.get("email"),
            phone=record.get("phone"),
            course_code=record["interested_course"],
            occurred_at=datetime.fromisoformat(record["submitted_at"]),
            raw=record,
        )
