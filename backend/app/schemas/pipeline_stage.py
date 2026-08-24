import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, model_validator


class PipelineStageUpdate(BaseModel):
    name: str | None = None
    sort_order: int | None = None
    win_probability_pct: int | None = None

    @model_validator(mode="after")
    def _check_win_probability(self) -> "PipelineStageUpdate":
        if self.win_probability_pct is not None and not 0 <= self.win_probability_pct <= 100:
            raise ValueError("win_probability_pct must be between 0 and 100")
        return self


class PipelineStageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    sort_order: int
    is_won: bool
    is_lost: bool
    win_probability_pct: int
    created_at: datetime
    updated_at: datetime
