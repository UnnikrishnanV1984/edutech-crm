from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        # crm_app — least-privilege runtime role (see alembic 0001). Never
        # connect here as crm_migrate.
        _engine = create_async_engine(settings.database_app_url, pool_pre_ping=True)
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _sessionmaker


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Plain session, no tenant context — only for code that genuinely has
    none (e.g. future admin/global-table tooling). Every tenant-scoped
    route must go through app.deps.tenant.get_tenant_context instead."""
    async with get_sessionmaker()() as session:
        yield session
