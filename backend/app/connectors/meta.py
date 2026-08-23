from datetime import datetime
from typing import Any

from app.connectors.base import RawLead, SeedFileConnector


class MetaConnector(SeedFileConnector):
    """Meta Lead Ads-shaped: a `field_data` array of {name, values}, the
    actual shape the Graph API returns for a leadgen object. A real
    integration (Phase 2) would override fetch_raw_leads to call the
    Graph API instead — normalize() stays the same."""

    source = "meta"
    seed_filename = "meta.json"

    def normalize(self, record: dict[str, Any]) -> RawLead:
        fields = {f["name"]: f["values"][0] for f in record["field_data"]}
        return RawLead(
            external_id=record["id"],
            full_name=fields["full_name"],
            email=fields.get("email"),
            phone=fields.get("phone_number"),
            course_code=fields["course_interest"],
            occurred_at=datetime.fromisoformat(record["created_time"]),
            raw=record,
        )
