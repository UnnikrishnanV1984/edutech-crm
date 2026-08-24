import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class DealCreate(BaseModel):
    course_id: uuid.UUID | None = None  # EdTech-specific — nullable for other verticals
    stage_id: uuid.UUID | None = None  # defaults to the first open stage
    owner_id: uuid.UUID | None = None  # defaults to the acting user
    account_id: uuid.UUID | None = None
    value: Decimal = Decimal("0")
    currency: str = "INR"


class DealUpdate(BaseModel):
    course_id: uuid.UUID | None = None
    stage_id: uuid.UUID | None = None
    owner_id: uuid.UUID | None = None
    account_id: uuid.UUID | None = None
    value: Decimal | None = None
    currency: str | None = None


class DealOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contact_id: uuid.UUID
    course_id: uuid.UUID | None
    stage_id: uuid.UUID
    owner_id: uuid.UUID
    account_id: uuid.UUID | None
    value: Decimal
    currency: str
    stage_changed_at: datetime
    created_at: datetime
    updated_at: datetime
