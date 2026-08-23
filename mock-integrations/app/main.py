"""Dev/test-only stand-in for the Meta Graph API, WhatsApp Cloud API, and
Google Ads API — never deployed in production (ARCHITECTURE.md §5/§6,
same annotation minio already carries). PHASE_2_PLAN.md §4.4.
"""

from fastapi import FastAPI

from app.routers import google, meta, whatsapp

app = FastAPI(title="mock-integrations", version="0.1.0")

app.include_router(meta.router)
app.include_router(whatsapp.router)
app.include_router(google.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
