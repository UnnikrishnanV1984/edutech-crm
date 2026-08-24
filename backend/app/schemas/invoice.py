import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, model_validator

# Client-triggerable statuses only — rework_requested and paid are
# system-only (set by the rework-stage hook and the payments service
# respectively, never accepted from a request body). See
# app/services/invoice_service.py's _CLIENT_ALLOWED_TRANSITIONS.
CLIENT_SETTABLE_STATUSES = ("sent", "cancelled")


class InvoiceCreate(BaseModel):
    invoice_number: str
    amount: Decimal
    due_date: date | None = None


class InvoiceUpdate(BaseModel):
    amount: Decimal | None = None
    due_date: date | None = None
    status: str | None = None

    @model_validator(mode="after")
    def _check_status(self) -> "InvoiceUpdate":
        if self.status is not None and self.status not in CLIENT_SETTABLE_STATUSES:
            raise ValueError(f"status must be one of {CLIENT_SETTABLE_STATUSES}")
        return self


class InvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    deal_id: uuid.UUID
    invoice_number: str
    amount: Decimal
    status: str
    issued_at: datetime | None
    due_date: date | None
    created_at: datetime
    updated_at: datetime
