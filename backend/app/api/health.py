from fastapi import APIRouter, status

# /health and /ready are the ONLY endpoints exempt from tenant validation
# (DEVELOPMENT_PLAN.md §4.1) — an explicit allowlist, not a missing
# dependency. Do not add another route here without going through the
# tenant-context dependency. /ready is added once the DB/Redis clients exist.
router = APIRouter(tags=["system"])


@router.get("/health", status_code=status.HTTP_200_OK)
async def health() -> dict:
    """Liveness — process is up. No DB touch, no auth."""
    return {"status": "ok"}
