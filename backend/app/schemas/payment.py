import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class PaymentCreate(BaseModel):
    amount: Decimal
    method: str | None = None
    paid_at: datetime | None = None  # defaults to now if omitted


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    invoice_id: uuid.UUID
    amount: Decimal
    paid_at: datetime
    method: str | None
    created_at: datetime
