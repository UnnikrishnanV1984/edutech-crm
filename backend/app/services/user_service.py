import uuid

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import VALIDATION_ERROR, ApiError
from app.models.user import User
from app.services.audit_log_service import record as record_audit_log


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


async def get_user(db: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID) -> User | None:
    result = await db.execute(select(User).where(User.tenant_id == tenant_id, User.id == user_id))
    return result.scalar_one_or_none()


async def update_user_manager(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user: User,
    manager_id: uuid.UUID | None,
    actor_id: uuid.UUID,
) -> User:
    """The manager-to-team mapping (REQUIREMENTS.md §5.3) — users.manager_id
    *is* the mapping, no separate table. manager_id=None clears it."""
    if manager_id is not None:
        manager = await get_user(db, tenant_id, manager_id)
        if manager is None or manager.role != "manager":
            raise ApiError(400, VALIDATION_ERROR, "manager_id must reference a manager")
    old_manager_id = user.manager_id
    user.manager_id = manager_id
    await db.flush()
    await db.refresh(user)
    await record_audit_log(
        db,
        tenant_id,
        actor_id,
        "user.manager_changed",
        "user",
        user.id,
        payload={
            "old_manager_id": str(old_manager_id) if old_manager_id else None,
            "new_manager_id": str(manager_id) if manager_id else None,
        },
    )
    return user


async def list_team_member_ids(
    db: AsyncSession, tenant_id: uuid.UUID, manager_id: uuid.UUID
) -> list[uuid.UUID]:
    """Direct reports only (users.manager_id == manager_id) — used by
    app/deps/scope.py to build a Manager's RowScope. Does not include the
    manager themselves; the caller adds that separately, since "my own
    rows" and "my team's rows" are conceptually distinct even though
    they're unioned in practice (PHASE_3_PLAN.md §4)."""
    result = await db.execute(
        select(User.id).where(User.tenant_id == tenant_id, User.manager_id == manager_id)
    )
    return list(result.scalars().all())


async def list_counselor_ids(db: AsyncSession, tenant_id: uuid.UUID) -> list[uuid.UUID]:
    """Ordered by created_at then id for a deterministic round-robin —
    used by app/connectors/ingestion_service.py to assign an owner to
    each seeded lead, since there's no acting HTTP user to default to."""
    result = await db.execute(
        select(User.id)
        .where(User.tenant_id == tenant_id, User.role == "counselor", User.status == "active")
        .order_by(User.created_at, User.id)
    )
    return list(result.scalars().all())
