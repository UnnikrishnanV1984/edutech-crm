import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.schemas.account import AccountCreate


async def create_account(
    db: AsyncSession, tenant_id: uuid.UUID, data: AccountCreate, default_owner_id: uuid.UUID
) -> Account:
    account = Account(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name=data.name,
        owner_id=data.owner_id or default_owner_id,
    )
    db.add(account)
    await db.flush()
    await db.refresh(account)
    return account


async def list_accounts(db: AsyncSession, tenant_id: uuid.UUID) -> list[Account]:
    result = await db.execute(
        select(Account).where(Account.tenant_id == tenant_id).order_by(Account.name)
    )
    return list(result.scalars().all())
