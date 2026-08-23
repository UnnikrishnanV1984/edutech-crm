import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import get_logger, request_id_ctx

logger = get_logger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assigns X-Request-Id and logs one line per request.

    The BFF is the only layer that talks to the browser, so in practice this
    header always arrives already set by the BFF (API_CONVENTIONS.md §1). A
    request that reaches FastAPI without one (e.g. direct debugging access)
    gets a freshly generated id rather than trusting an arbitrary caller-set
    value from an unauthenticated source.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = request_id
        token = request_id_ctx.set(request_id)
        start = time.monotonic()
        try:
            response = await call_next(request)
        finally:
            request_id_ctx.reset(token)
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        response.headers["X-Request-Id"] = request_id
        logger.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        return response
