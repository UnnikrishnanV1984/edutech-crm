import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, model_validator


class EscalationCreate(BaseModel):
    """Manual raise (REQUIREMENTS.md §4.1.3) — any authenticated role.
    assigned_to is never client-supplied; the service resolves it to the
    raiser's manager."""

    deal_id: uuid.UUID | None = None
    task_id: uuid.UUID | None = None
    reason: str

    @model_validator(mode="after")
    def _check_exactly_one_target(self) -> "EscalationCreate":
        if (self.deal_id is None) == (self.task_id is None):
            raise ValueError("exactly one of deal_id or task_id is required")
        return self


class EscalationUpdate(BaseModel):
    """status accepts the forward lifecycle steps this app drives
    (acknowledged, resolved, snoozed) — including a direct open->resolved
    edge (REQUIREMENTS.md §4.2: manager resolution should be a single
    action, not forced through acknowledge first). Reassignment is a
    separate concern (reassign_to) rather than a status value, so a
    reassigned escalation reopens as 'open' for its new assignee instead
    of dead-ending at a terminal 'reassigned' status with no further
    action possible. snoozed_until is required exactly when status is
    'snoozed' and forbidden otherwise — snoozing is the only status value
    that carries its own extra datum."""

    status: str | None = None
    resolution_note: str | None = None
    reassign_to: uuid.UUID | None = None
    snoozed_until: datetime | None = None

    @model_validator(mode="after")
    def _check_fields(self) -> "EscalationUpdate":
        if self.status is not None and self.status not in ("acknowledged", "resolved", "snoozed"):
            raise ValueError("status must be acknowledged, resolved, or snoozed")
        if self.status is None and self.reassign_to is None:
            raise ValueError("status or reassign_to is required")
        if self.status == "snoozed" and self.snoozed_until is None:
            raise ValueError("snoozed_until is required when status is snoozed")
        if self.status != "snoozed" and self.snoozed_until is not None:
            raise ValueError("snoozed_until is only accepted when status is snoozed")
        return self


class EscalationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: str
    deal_id: uuid.UUID | None
    task_id: uuid.UUID | None
    sla_state_id: uuid.UUID | None
    workflow_run_id: uuid.UUID | None
    raised_by: uuid.UUID | None
    assigned_to: uuid.UUID
    status: str
    reason: str | None
    resolution_note: str | None
    opened_at: datetime
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    snoozed_until: datetime | None
    was_reopened: bool
    # Enrichment, not stored on the row — populated by
    # escalation_service.list_escalations_enriched/get_escalation_enriched
    # (contact/rule/assignee names resolved via deal/task/workflow_run
    # joins, same batch-enrich shape as contact_service's list snapshot).
    contact_id: uuid.UUID | None = None
    contact_name: str | None = None
    rule_name: str | None = None
    assigned_to_name: str | None = None


class EscalationSummaryOut(BaseModel):
    open: int
    breaching_within_1h: int
    avg_resolve_minutes: float
    reopened: int
