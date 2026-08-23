import uuid

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def upsert_user(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    keycloak_sub: str,
    email: str,
    full_name: str | None,
    role: str,
) -> User:
    """JIT-provisions the users row for a Keycloak identity that has none
    yet, keyed on (tenant_id, keycloak_sub) — see DEVELOPMENT_PLAN.md §4.4.
    Keycloak stays the source of truth for identity/role; each call
    refreshes email/full_name/role from the (BFF-validated) token claims,
    so a role change in Keycloak takes effect on the caller's next request
    rather than needing a separate sync step.
    """
    stmt = pg_insert(User).values(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        keycloak_sub=keycloak_sub,
        email=email,
        full_name=full_name,
        role=role,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[User.tenant_id, User.keycloak_sub],
        set_={
            "email": stmt.excluded.email,
            "full_name": stmt.excluded.full_name,
            "role": stmt.excluded.role,
            "updated_at": func.now(),
        },
    ).returning(User)
    result = await db.execute(stmt)
    return result.scalar_one()
