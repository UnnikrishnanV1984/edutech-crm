import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def list_users(db: AsyncSession, tenant_id: uuid.UUID) -> list[User]:
    """Read-only tenant user directory — for owner/assignee pickers and
    resolving an id to a display name. Users themselves are JIT-provisioned
    on login (services/user_service.py), never created through this path."""
    result = await db.execute(
        select(User)
        .where(User.tenant_id == tenant_id, User.status == "active")
        .order_by(User.full_name, User.email)
    )
    return list(result.scalars().all())
