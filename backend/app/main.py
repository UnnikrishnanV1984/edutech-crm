import asyncio
import sys
from contextlib import asynccontextmanager

import redis.asyncio as redis
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import contacts, courses, deals, documents, health, me, pipeline_stages, tasks
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

    app = FastAPI(title="EdTech CRM API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(RequestContextMiddleware)

    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    app.include_router(health.router)
    app.include_router(me.router)
    app.include_router(contacts.router)
    app.include_router(courses.router)
    app.include_router(pipeline_stages.router)
    app.include_router(deals.router)
    app.include_router(tasks.router)
    app.include_router(documents.router)

    return app


app = create_app()
