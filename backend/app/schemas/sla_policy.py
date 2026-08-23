import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, model_validator

APPLIES_TO = ("stage_entry", "task_due")


class SlaPolicyCreate(BaseModel):
    name: str
    applies_to: str
    stage_id: uuid.UUID | None = None
    task_type: str | None = None
    target_minutes: int
    warning_threshold_pct: int = 80

    @model_validator(mode="after")
    def _check_fields(self) -> "SlaPolicyCreate":
        if self.applies_to not in APPLIES_TO:
            raise ValueError(f"applies_to must be one of {APPLIES_TO}")
        if self.applies_to == "stage_entry" and self.stage_id is None:
            raise ValueError("stage_id is required when applies_to is stage_entry")
        if self.applies_to == "task_due" and self.stage_id is not None:
            raise ValueError("stage_id must be omitted when applies_to is task_due")
        if self.target_minutes <= 0:
            raise ValueError("target_minutes must be positive")
        if not 1 <= self.warning_threshold_pct <= 99:
            raise ValueError("warning_threshold_pct must be between 1 and 99")
        return self


class SlaPolicyUpdate(BaseModel):
    name: str | None = None
    target_minutes: int | None = None
    warning_threshold_pct: int | None = None
    status: str | None = None

    @model_validator(mode="after")
    def _check_fields(self) -> "SlaPolicyUpdate":
        if self.target_minutes is not None and self.target_minutes <= 0:
            raise ValueError("target_minutes must be positive")
        if self.warning_threshold_pct is not None and not 1 <= self.warning_threshold_pct <= 99:
            raise ValueError("warning_threshold_pct must be between 1 and 99")
        if self.status is not None and self.status not in ("active", "disabled"):
            raise ValueError("status must be active or disabled")
        return self


class SlaPolicyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    applies_to: str
    stage_id: uuid.UUID | None
    task_type: str | None
    target_minutes: int
    warning_threshold_pct: int
    status: str
    created_at: datetime
    updated_at: datetime
