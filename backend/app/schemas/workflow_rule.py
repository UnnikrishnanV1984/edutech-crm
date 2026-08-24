import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator

TRIGGER_TYPES = ("stage_changed", "lead_created", "task_overdue", "elapsed_time")
ACTION_TYPES = (
    "assign_round_robin",
    "create_task",
    "change_stage",
    "notify_manager",
    "raise_escalation",
    "send_message",
)


class WorkflowRuleCreate(BaseModel):
    name: str
    trigger_type: str
    trigger_config: dict[str, Any] = {}
    conditions: list[dict[str, Any]] = []
    actions: list[dict[str, Any]]
    status: str = "draft"
    """Admin-only choice — a Manager's request always gets forced to
    pending_approval regardless of this value (REQUIREMENTS.md §2.4),
    enforced in the route/service, not trusted from the client."""

    @model_validator(mode="after")
    def _check_fields(self) -> "WorkflowRuleCreate":
        if self.trigger_type not in TRIGGER_TYPES:
            raise ValueError(f"trigger_type must be one of {TRIGGER_TYPES}")
        if not self.actions:
            raise ValueError("at least one action is required")
        for action in self.actions:
            if action.get("type") not in ACTION_TYPES:
                raise ValueError(f"action type must be one of {ACTION_TYPES}")
        if self.status not in ("draft", "active"):
            raise ValueError("status must be draft or active")
        return self


class WorkflowRuleDecision(BaseModel):
    """PATCH body for the admin approve/reject/edit endpoint."""

    status: str | None = None
    name: str | None = None
    trigger_config: dict[str, Any] | None = None
    conditions: list[dict[str, Any]] | None = None
    actions: list[dict[str, Any]] | None = None

    @model_validator(mode="after")
    def _check_status(self) -> "WorkflowRuleDecision":
        if self.status is not None and self.status not in ("active", "disabled", "draft"):
            raise ValueError("status must be active, disabled, or draft")
        return self


class WorkflowRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    trigger_type: str
    trigger_config: dict[str, Any]
    conditions: list[Any]
    actions: list[Any]
    status: str
    created_by: uuid.UUID
    approved_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
