"""The connector interface every lead source implements.

For now every concrete connector (meta.py, google.py, web.py, whatsapp.py)
is a SeedFileConnector, reading a checked-in JSON file shaped like that
platform's actual payload instead of calling a live API — see
SEED_CONNECTORS_PLAN.md. Swapping a source to the real integration later
(FEATURES_AND_PLAN.md Phase 2) means overriding fetch_raw_leads (or just
_load) to call the platform's API instead; normalize()'s contract and
everything downstream (ingestion_service.py) stays the same.
"""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

SEED_DATA_DIR = Path(__file__).parent / "seed_data"


@dataclass(frozen=True)
class RawLead:
    external_id: str
    full_name: str
    email: str | None
    phone: str | None
    course_code: str | None
    """None when the source payload carries no course-interest field —
    app/services/lead_ingestion_service.py still creates the contact in
    that case, just without a deal (PHASE_2_PLAN.md acceptance
    criterion 10)."""
    occurred_at: datetime
    raw: dict[str, Any]


class LeadConnector(ABC):
    source: str
    """One of contacts.lead_source's CHECK values (meta/google/web/whatsapp)."""

    @abstractmethod
    def fetch_raw_leads(self) -> list[RawLead]: ...


class SeedFileConnector(LeadConnector):
    seed_filename: str

    def fetch_raw_leads(self) -> list[RawLead]:
        path = SEED_DATA_DIR / self.seed_filename
        with path.open(encoding="utf-8") as f:
            records = json.load(f)
        return [self.normalize(record) for record in records]

    @abstractmethod
    def normalize(self, record: dict[str, Any]) -> RawLead:
        """Maps one platform-shaped raw record into a RawLead. This is the
        step a real Phase 2 connector would also need — kept real here
        rather than reading pre-normalized data, so it actually exercises
        the mapping logic the future integration will share."""
        ...
