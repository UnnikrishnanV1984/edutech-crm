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


@dataclass
class TenantContext:
    tenant: Tenant
    user_id: str
    db: AsyncSession


async def get_tenant_context(
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> AsyncGenerator[TenantContext, None]:
    """Required by every tenant-scoped route (CLAUDE.md rule 3). Trusts
    X-Tenant-Id / X-User-Id only because the BFF has already validated them
    against Keycloak and stripped any client-supplied copies (CLAUDE.md
    rule 7) — FastAPI does not re-validate a token here, it trusts the BFF.

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

            tenant_token = tenant_id_ctx.set(str(tenant_uuid))
            user_token = user_id_ctx.set(x_user_id)
            try:
                yield TenantContext(tenant=tenant, user_id=x_user_id, db=session)
            finally:
                tenant_id_ctx.reset(tenant_token)
                user_id_ctx.reset(user_token)
    finally:
        await session.close()
