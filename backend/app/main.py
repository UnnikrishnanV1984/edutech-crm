import asyncio
import sys
from contextlib import asynccontextmanager

import redis.asyncio as redis
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import (
    accounts,
    contacts,
    courses,
    deals,
    documents,
    escalations,
    follow_up_flags,
    health,
    invoices,
    lead_source_connections,
    me,
    payments,
    pipeline_stage_templates,
    pipeline_stages,
    reports,
    sla_policies,
    tasks,
    users,
    workflow_rules,
)
from app.core.config import get_settings
from app.core.errors import (
    ApiError,
    api_error_handler,
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.db.session import get_engine
from app.webhooks import meta as meta_webhooks
from app.webhooks import web as web_webhooks
from app.webhooks import whatsapp as whatsapp_webhooks

if sys.platform == "win32":
    # psycopg3's async mode cannot run under ProactorEventLoop, Windows's
    # asyncio default. Only relevant for `uvicorn app.main:app` run directly
    # on a Windows host — the Linux containers used by docker-compose /
    # production are unaffected. uvicorn's default `--loop auto` forces
    # ProactorEventLoop on win32 regardless of policy, so this also
    # requires running uvicorn with `--loop none` (see CLAUDE.md) so it
    # falls back to asyncio.new_event_loop() under this policy instead.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.redis = redis.from_url(settings.redis_url)
    yield
    await app.state.redis.aclose()
    await get_engine().dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title="OpenFunnel API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(RequestContextMiddleware)

    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    app.include_router(health.router)
    app.include_router(me.router)
    app.include_router(accounts.router)
    app.include_router(contacts.router)
    app.include_router(courses.router)
    app.include_router(pipeline_stages.router)
    app.include_router(pipeline_stage_templates.router)
    app.include_router(deals.router)
    app.include_router(invoices.router)
    app.include_router(payments.router)
    app.include_router(tasks.router)
    app.include_router(documents.router)
    app.include_router(users.router)
    app.include_router(lead_source_connections.router)
    app.include_router(sla_policies.router)
    app.include_router(escalations.router)
    app.include_router(follow_up_flags.router)
    app.include_router(workflow_rules.router)
    app.include_router(reports.router)

    # Public — bypass the BFF entirely, PHASE_2_PLAN.md §4.2.
    app.include_router(meta_webhooks.router)
    app.include_router(whatsapp_webhooks.router)
    app.include_router(web_webhooks.router)

    return app


app = create_app()
