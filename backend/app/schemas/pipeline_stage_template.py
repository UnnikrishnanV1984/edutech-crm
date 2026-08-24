import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

# No Create/Update schema — this table has no tenant-facing write path,
# ever (PIPELINE_AND_REVENUE.md §2.6's architect review). Output only.


class PipelineStageTemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    category: str
    default_sort_order: int
    is_won: bool
    is_lost: bool
    is_invoice_stage: bool
    is_rework_stage: bool
    default_win_probability_pct: int
    created_at: datetime
