import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

ActivityChannel = Literal["call", "email", "whatsapp", "note"]


class ActivityCreate(BaseModel):
    """Manual logging (Contact Detail's "Log activity" action) — the
    only Activity type a request handler ever writes directly; every
    other type (deal_stage_changed, lead_captured) is system-generated
    from inside a service function, never from a client-supplied
    payload."""

    note: str
    channel: ActivityChannel = "note"


class ActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contact_id: uuid.UUID
    deal_id: uuid.UUID | None
    type: str
    actor_id: uuid.UUID
    payload: dict[str, Any] | None
    created_at: datetime
