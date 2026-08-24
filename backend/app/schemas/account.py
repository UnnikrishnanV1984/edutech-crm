import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AccountCreate(BaseModel):
    name: str
    owner_id: uuid.UUID | None = None  # defaults to the acting user


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    owner_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
