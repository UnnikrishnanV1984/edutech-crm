from fastapi import APIRouter, Request, status
from sqlalchemy import text

from app.db.session import get_engine

# /health and /ready are the ONLY endpoints exempt from tenant validation
# (DEVELOPMENT_PLAN.md §4.1) — an explicit allowlist, not a missing
# dependency. Do not add another route here without going through the
# tenant-context dependency.
router = APIRouter(tags=["system"])


@router.get("/health", status_code=status.HTTP_200_OK)
async def health() -> dict:
    """Liveness — process is up. No DB touch, no auth."""
    return {"status": "ok"}


@router.get("/ready")
async def ready(request: Request) -> dict:
    """Readiness — DB and Redis reachable."""
    engine = get_engine()
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))

    await request.app.state.redis.ping()

    return {"status": "ok"}
