import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DealCreate(BaseModel):
    course_id: uuid.UUID
    stage_id: uuid.UUID | None = None  # defaults to the first open stage
    owner_id: uuid.UUID | None = None  # defaults to the acting user


class DealUpdate(BaseModel):
    course_id: uuid.UUID | None = None
    stage_id: uuid.UUID | None = None
    owner_id: uuid.UUID | None = None


class DealOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contact_id: uuid.UUID
    course_id: uuid.UUID
    stage_id: uuid.UUID
    owner_id: uuid.UUID
    stage_changed_at: datetime
    created_at: datetime
    updated_at: datetime
