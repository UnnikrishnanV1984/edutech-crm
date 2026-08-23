import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass

from fastapi import Header
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import UNAUTHORIZED, ApiError
from app.core.logging import tenant_id_ctx, user_id_ctx
from app.db.session import get_sessionmaker
from app.models.tenant import Tenant
from app.models.user import User
from app.services.user_service import upsert_user

VALID_ROLES = ("admin", "manager", "counselor")


@dataclass
class TenantContext:
    tenant: Tenant
    user_id: str
    user_email: str
    user_full_name: str | None
    user_role: str
    db: AsyncSession
    user: User
    """The resolved internal users row (JIT-provisioned if this is the
    caller's first request) — use user.id, not user_id, for any FK
    referencing users.id (owner_id, assignee_id, etc.). user_id above is
    the Keycloak sub, a different UUID space entirely."""


async def get_tenant_context(
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_user_email: str | None = Header(default=None, alias="X-User-Email"),
    x_user_name: str | None = Header(default=None, alias="X-User-Name"),
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
) -> AsyncGenerator[TenantContext, None]:
    """Required by every tenant-scoped route (CLAUDE.md rule 3). Trusts
    these headers only because the BFF has already validated the caller's
    token against Keycloak and stripped any client-supplied copies
    (CLAUDE.md rule 7) — FastAPI does not re-validate a token here, it
    trusts the BFF. X-User-Email/-Name/-Role extend the header set beyond
    ARCHITECTURE.md's original three (X-Tenant-Id/X-User-Id/X-Request-Id) —
    see API_CONVENTIONS.md §1 and DEVELOPMENT_PLAN.md §4.4 for why the JIT
    user upsert needs them.

    /health and /ready are the only routes that don't depend on this.
    """
    if not x_tenant_id:
        raise ApiError(401, UNAUTHORIZED, "Missing X-Tenant-Id")
    try:
        tenant_uuid = uuid.UUID(x_tenant_id)
    except ValueError as exc:
        raise ApiError(401, UNAUTHORIZED, "Malformed X-Tenant-Id") from exc

    if not x_user_id:
        raise ApiError(401, UNAUTHORIZED, "Missing X-User-Id")
    if not x_user_email:
        raise ApiError(401, UNAUTHORIZED, "Missing X-User-Email")
    if not x_user_role:
        raise ApiError(401, UNAUTHORIZED, "Missing X-User-Role")
    if x_user_role not in VALID_ROLES:
        raise ApiError(401, UNAUTHORIZED, "Unrecognized X-User-Role")

    session = get_sessionmaker()()
    try:
        async with session.begin():
            # tenants has no RLS — the one query that runs before
            # app.tenant_id is set (DATABASE_SCHEMA.md §1).
            result = await session.execute(
                select(Tenant).where(Tenant.id == tenant_uuid, Tenant.status == "active")
            )
            tenant = result.scalar_one_or_none()
            if tenant is None:
                # 401, not 404 — don't let a caller probe which tenant UUIDs
                # exist (DEVELOPMENT_PLAN.md §4.1).
                raise ApiError(401, UNAUTHORIZED, "Unknown or inactive tenant")

            # SET LOCAL semantics (is_local=true) — scoped to this
            # transaction only, safe under a future PgBouncer transaction
            # pool (DEVELOPMENT_PLAN.md §3.3).
            await session.execute(
                text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_uuid)},
            )

            # JIT-provisions/refreshes the internal users row for every
            # authenticated request, not just /api/v1/me — endpoints that
            # need "the acting user" as a foreign key (owner_id,
            # assignee_id, ...) need users.id, which lives in a different
            # UUID space than the Keycloak sub above.
            user = await upsert_user(
                db=session,
                tenant_id=tenant_uuid,
                keycloak_sub=x_user_id,
                email=x_user_email,
                full_name=x_user_name,
                role=x_user_role,
            )

            tenant_token = tenant_id_ctx.set(str(tenant_uuid))
            user_token = user_id_ctx.set(x_user_id)
            try:
                yield TenantContext(
                    tenant=tenant,
                    user_id=x_user_id,
                    user_email=x_user_email,
                    user_full_name=x_user_name,
                    user_role=x_user_role,
                    db=session,
                    user=user,
                )
            finally:
                tenant_id_ctx.reset(tenant_token)
                user_id_ctx.reset(user_token)
    finally:
        await session.close()
