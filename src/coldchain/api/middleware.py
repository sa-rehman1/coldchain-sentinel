"""HTTP correlation and request logging middleware."""

import logging
import time
from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


def normalize_correlation_id(candidate: str | None) -> str:
    """Accept UUID correlation IDs and replace malformed input."""

    if candidate:
        try:
            return str(UUID(candidate))
        except ValueError:
            pass
    return str(uuid4())


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        correlation_id = normalize_correlation_id(request.headers.get("X-Correlation-ID"))
        request.state.correlation_id = correlation_id
        started = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        response.headers["X-Correlation-ID"] = correlation_id
        logger.info(
            "http_request_completed",
            extra={
                "correlationId": correlation_id,
                "method": request.method,
                "path": request.url.path,
                "statusCode": response.status_code,
                "durationMs": elapsed_ms,
            },
        )
        return response
