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
    is_invoice_stage: bool = False
    is_rework_stage: bool = False


class PipelineStageReorder(BaseModel):
    stage_ids: list[uuid.UUID]


# PIPELINE_CONFIG_RESET_PLAN.md §5.1 — full-replacement contract, not a
# diff, deliberately mirroring PipelineStageReorder's "always send the
# complete list" precedent. Array order is the new sort_order. An entry
# with `id` is an existing stage (only `name` is read for it — the
# won/lost/invoice/rework flags are creation-only, same rule as the
# single-stage PATCH, so they're accepted-and-ignored here rather than
# rejected outright); an entry with no `id` is a new stage, using the same
# fields as PipelineStageCreate. Any current tenant stage whose id is
# absent from the list is a delete.
class PipelineStageBatchEntry(BaseModel):
    id: uuid.UUID | None = None
    name: str
    is_won: bool = False
    is_lost: bool = False
    is_invoice_stage: bool = False
    is_rework_stage: bool = False


class PipelineStageBatchUpdate(BaseModel):
    stages: list[PipelineStageBatchEntry]


# PIPELINE_CONFIG_RESET_PLAN.md §5.2 — the exact phrase is checked here
# too, not just disabled-until-typed-correctly on the frontend, so a
# hand-crafted request without it is rejected the same way any other
# malformed body is.
RESET_TO_DEFAULT_CONFIRM_PHRASE = "RESET TO DEFAULT"


class PipelineStageResetToDefault(BaseModel):
    confirm: str

    @model_validator(mode="after")
    def _check_confirm_phrase(self) -> "PipelineStageResetToDefault":
        if self.confirm != RESET_TO_DEFAULT_CONFIRM_PHRASE:
            raise ValueError(f'confirm must be exactly "{RESET_TO_DEFAULT_CONFIRM_PHRASE}"')
        return self


class PipelineStageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    sort_order: int
    is_won: bool
    is_lost: bool
    is_invoice_stage: bool
    is_rework_stage: bool
    win_probability_pct: int
    created_at: datetime
    updated_at: datetime
