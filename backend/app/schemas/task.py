import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

TASK_STATUSES = ("open", "done")


class TaskCreate(BaseModel):
    contact_id: uuid.UUID
    deal_id: uuid.UUID | None = None
    assignee_id: uuid.UUID | None = None  # defaults to the acting user
    title: str
    description: str | None = None
    due_at: datetime | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    due_at: datetime | None = None
    assignee_id: uuid.UUID | None = None
    status: str | None = None  # "open" | "done" — drives completed_at


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contact_id: uuid.UUID
    deal_id: uuid.UUID | None
    assignee_id: uuid.UUID
    title: str
    description: str | None
    due_at: datetime | None
    status: str
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
