"""
API middleware for request tracing and performance monitoring.

Every inbound request gets a unique ``X-Request-ID`` header.  This ID is
injected into structlog's context vars so that every log line emitted during
that request (including deep inside the agent graph) carries the correlation
ID.  This is the same pattern used in production observability stacks.
"""

from __future__ import annotations

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.observability.logging import get_logger

logger = get_logger(__name__)


class RequestTracingMiddleware(BaseHTTPMiddleware):
    """
    Injects a unique request ID and measures wall-clock latency.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        start = time.perf_counter()

        # Bind the request ID to structlog context for the duration of this request
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        response: Response | None = None
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("unhandled_request_error")
            raise
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.info(
                "request_complete",
                status_code=response.status_code if response is not None else 500,
                elapsed_ms=round(elapsed_ms, 2),
            )

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.2f}"
        return response
