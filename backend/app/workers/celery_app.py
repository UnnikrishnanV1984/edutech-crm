"""Celery app — first real use of the /backend/app/workers package
DEVELOPMENT_PLAN.md §1/§9 reserved back in Phase 0 ("Celery, not
BullMQ," already decided, not re-litigated here — PHASE_3_PLAN.md §1).
Redis doubles as broker and result backend, the same required infra
this repo already runs; no new stateful service.

Two Compose services run this: `worker` (`celery -A app.workers.celery_app
worker`) executes tasks, `beat` (`celery -A app.workers.celery_app beat`)
fires the periodic dispatchers on the schedule below. Same `backend`
Docker image as the API process, different CMD.
"""

import asyncio
import logging
import sys

from celery import Celery

from app.core.config import get_settings

if sys.platform == "win32":
    # Same constraint as app/main.py — a Celery worker process run
    # directly on a Windows host needs the same event-loop-policy guard
    # any other standalone async entrypoint in this repo needs.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Celery's own --loglevel setup, not app/core/logging.py's
# configure_logging (that only runs in the FastAPI process, never
# imported here) — so the same httpx-URL-logging suppression
# app/core/logging.py applies for the API process has to be repeated
# here for worker/beat. Needed since app/workers/conversions.py sends
# Meta's access_token as a query param (the real Conversions API's
# actual contract), which httpx's own INFO-level request logging would
# otherwise put in plain worker log output (CLAUDE.md rule 5).
logging.getLogger("httpx").setLevel(logging.WARNING)

_settings = get_settings()

celery_app = Celery(
    "edutech_crm",
    broker=_settings.redis_url,
    backend=_settings.redis_url,
    include=["app.workers.sla", "app.workers.rules", "app.workers.conversions"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Tenant tasks each open their own short-lived DB session (mirrors
    # app/connectors/ingestion_service.py) — no reason for a worker to
    # hold one open longer than a single task.
    worker_prefetch_multiplier=1,
)

# Both periodic dispatchers fan out one task per tenant rather than
# looping over every tenant inside themselves — PHASE_3_PLAN.md §8: a
# slow or failing tenant can't block another's computation.
celery_app.conf.beat_schedule = {
    "dispatch-sla-computation": {
        "task": "app.workers.sla.dispatch_sla_computation",
        "schedule": 300.0,
    },
    "dispatch-time-based-rule-scan": {
        "task": "app.workers.rules.dispatch_time_based_scan",
        "schedule": 300.0,
    },
}
