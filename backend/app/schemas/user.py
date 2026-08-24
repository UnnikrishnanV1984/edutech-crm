import uuid

from pydantic import BaseModel, ConfigDict


class TenantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str | None
    role: str
    manager_id: uuid.UUID | None
    status: str
    territory: str | None


class UserUpdate(BaseModel):
    """PATCH /api/v1/users/{id} — admin-only (PHASE_3_PLAN.md §4).

    Deliberately does NOT include `role`, despite PHASE_3_PLAN.md §4
    sketching one — implementing it surfaced a real conflict the plan
    missed: app/services/user_service.py's upsert_user refreshes `role`
    from the Keycloak token claim on every authenticated request (JIT
    provisioning, DEVELOPMENT_PLAN.md §4.4), so an in-app role change
    here would be silently reverted the next time that user made any
    request. Keycloak remains the sole source of truth for role; a real
    "change a user's role" feature needs a Keycloak Admin API
    integration, which is new scope this plan didn't budget for.
    `manager_id`/`territory` are settable here — Keycloak has no concept
    of either, so this app is the only source of truth for them.
    """

    manager_id: uuid.UUID | None = None
    territory: str | None = None


class MeData(BaseModel):
    user: UserOut
    tenant: TenantOut
