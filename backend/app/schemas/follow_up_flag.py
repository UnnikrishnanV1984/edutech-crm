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


class FollowUpFlagUpdate(BaseModel):
    """Body-optional PATCH: an empty body resolves the flag (unchanged
    behavior — FollowUpFlagCard.tsx's existing resolveFollowUpFlag call
    sends no body at all). remind_on present instead means "snooze" —
    move the reminder later without resolving. The two are mutually
    exclusive actions, not combinable in one call."""

    remind_on: date | None = None


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
    # Enrichment, not stored on the row — populated by
    # follow_up_flag_service.enrich_flags. resolved_contact_id is the
    # actual contact this flag concerns even when raised against a deal
    # (contact_id above stays NULL in that case, per
    # ck_follow_up_flags_target's exactly-one-of deal_id/contact_id).
    resolved_contact_id: uuid.UUID | None = None
    contact_name: str | None = None
    manager_name: str | None = None
