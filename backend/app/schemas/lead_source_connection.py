import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, model_validator

SOURCES = ("meta", "google", "whatsapp", "web")
STATUSES = ("active", "disabled")


class LeadSourceConnectionCreate(BaseModel):
    source: str
    # Ignored for source="web" — the server generates a public embed key
    # instead (PHASE_2_PLAN.md §3/§4.1).
    external_account_id: str | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    token_expires_at: datetime | None = None

    @model_validator(mode="after")
    def _check_required_fields(self) -> "LeadSourceConnectionCreate":
        if self.source not in SOURCES:
            raise ValueError(f"source must be one of {SOURCES}")
        if self.source != "web":
            if not self.external_account_id:
                raise ValueError("external_account_id is required for this source")
            if not self.access_token:
                raise ValueError("access_token is required for this source")
        return self


class LeadSourceConnectionUpdate(BaseModel):
    status: str

    @model_validator(mode="after")
    def _check_status(self) -> "LeadSourceConnectionUpdate":
        if self.status not in STATUSES:
            raise ValueError(f"status must be one of {STATUSES}")
        return self


class LeadSourceConnectionOut(BaseModel):
    """Never includes decrypted (or even encrypted) token material —
    PHASE_2_PLAN.md §4.1."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: str
    external_account_id: str
    status: str
    token_expires_at: datetime | None
    last_synced_at: datetime | None
    created_at: datetime
    updated_at: datetime
