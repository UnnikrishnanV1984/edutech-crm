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


class PipelineStageCreate(BaseModel):
    name: str
    # Settable only at creation — matching PipelineStageUpdate's
    # deliberate exclusion of these from PATCH (later phases read
    # is_won/is_lost as a stable signal: forecast's stage-weighted
    # headcount, ARCHITECTURE.md Sec7d's conversion-signal trigger).
    # sort_order is not client-settable here — always appended at the
    # end (ADMIN_UX_IMPROVEMENTS_PLAN.md Sec4.2); use the reorder
    # endpoint afterward.
    is_won: bool = False
    is_lost: bool = False


class PipelineStageReorder(BaseModel):
    stage_ids: list[uuid.UUID]


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
