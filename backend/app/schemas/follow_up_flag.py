import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, model_validator


class FollowUpFlagCreate(BaseModel):
    deal_id: uuid.UUID | None = None
    contact_id: uuid.UUID | None = None
    note: str
    remind_on: date

    @model_validator(mode="after")
    def _check_exactly_one_target(self) -> "FollowUpFlagCreate":
        if (self.deal_id is None) == (self.contact_id is None):
            raise ValueError("exactly one of deal_id or contact_id is required")
        return self


class FollowUpFlagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    manager_id: uuid.UUID
    deal_id: uuid.UUID | None
    contact_id: uuid.UUID | None
    note: str
    remind_on: date
    resolved_at: datetime | None
    created_at: datetime
