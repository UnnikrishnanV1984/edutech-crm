from datetime import datetime
from typing import Any

from app.connectors.base import RawLead, SeedFileConnector


class GoogleConnector(SeedFileConnector):
    """Google Ads lead form extension-shaped: a `userColumnData` array of
    {columnId, stringValue}, the actual shape Google's lead form webhook
    payload uses. A real integration (Phase 2) would override
    fetch_raw_leads to pull from Google's API instead — normalize() stays
    the same."""

    source = "google"
    seed_filename = "google.json"

    def normalize(self, record: dict[str, Any]) -> RawLead:
        columns = {c["columnId"]: c["stringValue"] for c in record["userColumnData"]}
        return RawLead(
            external_id=record["leadId"],
            full_name=columns["FULL_NAME"],
            email=columns.get("EMAIL"),
            phone=columns.get("PHONE_NUMBER"),
            course_code=columns.get("COURSE_CODE"),
            occurred_at=datetime.fromisoformat(record["createTime"]),
            raw=record,
        )
