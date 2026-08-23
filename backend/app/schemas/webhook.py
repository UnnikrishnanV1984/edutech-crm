from pydantic import BaseModel


class WebLeadCreate(BaseModel):
    """Body of the embeddable web-form endpoint (POST /webhooks/web) — the
    one lead-capture path with no platform-supplied idempotency key
    (PHASE_2_PLAN.md §6 step 15). idempotency_key is optional so an
    embedding form's own retry logic can supply one; without it, a
    network-level retry of the same real submission can create a
    duplicate contact — an accepted limitation for an anonymous public
    form, not solved further in this phase."""

    embed_key: str
    full_name: str
    email: str | None = None
    phone: str | None = None
    course_code: str | None = None
    idempotency_key: str | None = None
