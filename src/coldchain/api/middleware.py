"""HTTP correlation and request logging middleware."""

import logging
import time
from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from coldchain.observability.metrics import metrics
from coldchain.observability.tracing import span

logger = logging.getLogger(__name__)

_ROUTES = (
    "/metrics",
    "/api/v1/health/live",
    "/api/v1/health/ready",
    "/api/v1/health/ai",
    "/api/v1/incidents",
    "/api/v1/incidents/{incident_id}",
    "/api/v1/incidents/{incident_id}/timeline",
    "/api/v1/incidents/{incident_id}/recommendations/{recommendation_id}/approve",
    "/api/v1/incidents/{incident_id}/recommendations/{recommendation_id}/reject",
    "/api/v1/commands/{command_id}",
)


def normalize_route(path: str) -> str:
    """Collapse request paths into a fixed metric-label vocabulary."""

    if path in _ROUTES:
        return path
    if path.startswith("/api/v1/incidents/"):
        if path.endswith("/timeline"):
            return "/api/v1/incidents/{incident_id}/timeline"
        if "/recommendations/" in path and path.endswith("/approve"):
            return "/api/v1/incidents/{incident_id}/recommendations/{recommendation_id}/approve"
        if "/recommendations/" in path and path.endswith("/reject"):
            return "/api/v1/incidents/{incident_id}/recommendations/{recommendation_id}/reject"
        return "/api/v1/incidents/{incident_id}"
    if path.startswith("/api/v1/commands/"):
        return "/api/v1/commands/{command_id}"
    return "unmatched"


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
        route = normalize_route(request.url.path)
        method = (
            request.method
            if request.method in {"GET", "POST", "PUT", "PATCH", "DELETE"}
            else "OTHER"
        )
        active = metrics.api_active.labels(method=method, route=route)
        active.inc()
        try:
            with span(
                "http.request",
                attributes={"http.request.method": method, "http.route": route},
            ) as current_span:
                response = await call_next(request)
                current_span.set_attribute("http.response.status_code", response.status_code)
        finally:
            active.dec()
        elapsed_seconds = time.perf_counter() - started
        elapsed_ms = round(elapsed_seconds * 1000, 3)
        status_class = f"{response.status_code // 100}xx"
        metrics.api_requests.labels(method=method, route=route, status_class=status_class).inc()
        metrics.api_duration.labels(method=method, route=route).observe(elapsed_seconds)
        response.headers["X-Correlation-ID"] = correlation_id
        logger.info(
            "http_request_completed",
            extra={
                "correlationId": correlation_id,
                "component": "api",
                "eventName": "http_request_completed",
                "method": method,
                "route": route,
                "statusCode": response.status_code,
                "durationMs": elapsed_ms,
            },
        )
        return response
