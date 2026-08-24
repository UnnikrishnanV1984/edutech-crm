import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

LEAD_SOURCES = ("meta", "google", "web", "whatsapp", "manual")
CONTACT_STATUSES = ("active", "archived")

# Deliberately not pydantic's EmailStr: its underlying email_validator
# package rejects RFC 2606 reserved test domains (example.test,
# *.invalid, ...) by default — exactly the convention Phase 0's Keycloak
# seed data and every existing test fixture use
# (counselor.a@example.test). A basic shape check is enough here; nothing
# in Phase 1 sends verification emails or otherwise needs full RFC 5321
# validation.
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _validate_email(value: str | None) -> str | None:
    if value is not None and not _EMAIL_RE.match(value):
        raise ValueError("not a valid email address")
    return value


class ContactCreate(BaseModel):
    full_name: str
    email: str | None = None
    phone: str | None = None
    lead_source: str
    owner_id: uuid.UUID | None = None  # defaults to the acting user
    territory: str | None = None  # admin-set — GAP_FIXES_PLAN.md item 3

    _check_email = field_validator("email")(_validate_email)


class ContactUpdate(BaseModel):
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    lead_source: str | None = None
    owner_id: uuid.UUID | None = None
    status: str | None = None
    territory: str | None = None

    _check_email = field_validator("email")(_validate_email)


class ContactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    email: str | None
    phone: str | None
    lead_source: str
    owner_id: uuid.UUID
    status: str
    territory: str | None
    created_at: datetime
    updated_at: datetime
