import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contact_id: uuid.UUID
    deal_id: uuid.UUID | None
    type: str
    actor_id: uuid.UUID
    payload: dict[str, Any] | None
    created_at: datetime
