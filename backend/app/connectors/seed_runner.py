"""`python -m app.connectors.seed_runner` — dev-only entrypoint that runs
every lead connector for every active tenant. Invoked by
docker-entrypoint.sh inside its existing ENVIRONMENT=development gate,
after app/db/seed.py has seeded tenants and pre-provisioned dev staff —
never invoked otherwise.
"""

import asyncio
import logging
import sys
import uuid

from sqlalchemy import select

from app.connectors.ingestion_service import ingest_all
from app.db.session import get_engine, get_sessionmaker
from app.models.tenant import Tenant

logger = logging.getLogger(__name__)

if sys.platform == "win32":
    # Same constraint as app/main.py and app/db/seed.py — this module is
    # its own standalone async entrypoint.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def _active_tenant_ids() -> list[uuid.UUID]:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as db:
        result = await db.execute(select(Tenant.id).where(Tenant.status == "active"))
        return list(result.scalars().all())


async def run() -> None:
    for tenant_id in await _active_tenant_ids():
        count = await ingest_all(tenant_id)
        logger.info("seed_ingestion_complete tenant_id=%s ingested=%s", tenant_id, count)
    await get_engine().dispose()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
