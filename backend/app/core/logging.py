import logging
import sys
from contextvars import ContextVar

import structlog

# Populated per-request by the tenant-context dependency / request-id middleware.
# Only tenant_id and user_id are logged (CLAUDE.md rule 5) — never email, phone,
# or document contents. Do not add PII fields to this context.
request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
tenant_id_ctx: ContextVar[str | None] = ContextVar("tenant_id", default=None)
user_id_ctx: ContextVar[str | None] = ContextVar("user_id", default=None)


def _inject_context(logger, method_name, event_dict):
    request_id = request_id_ctx.get()
    tenant_id = tenant_id_ctx.get()
    user_id = user_id_ctx.get()
    if request_id:
        event_dict["request_id"] = request_id
    if tenant_id:
        event_dict["tenant_id"] = tenant_id
    if user_id:
        event_dict["user_id"] = user_id
    return event_dict


def configure_logging(log_level: str) -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )
    # httpx logs each outbound request's full URL at INFO by default —
    # harmless for most calls in this app, but app/workers/conversions.py
    # sends Meta's access_token as a query param (the real Conversions
    # API's actual contract, not a choice made here — ARCHITECTURE.md
    # §7d), which would otherwise put a decrypted credential in plain
    # log output (CLAUDE.md rule 5). Silencing httpx's own logger, not
    # this app's structlog output.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            _inject_context,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str):
    return structlog.get_logger(name)
