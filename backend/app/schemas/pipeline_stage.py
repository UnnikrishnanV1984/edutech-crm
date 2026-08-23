import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PipelineStageUpdate(BaseModel):
    name: str | None = None
    sort_order: int | None = None


class PipelineStageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    sort_order: int
    is_won: bool
    is_lost: bool
    created_at: datetime
    updated_at: datetime
