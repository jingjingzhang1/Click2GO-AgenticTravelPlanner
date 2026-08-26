"""
Request context middleware
==========================
Assigns a correlation ID to every request (honouring an inbound
``X-Request-ID`` if present), times the request, records metrics, and emits a
single structured access-log line per request. The ID is echoed back in the
``X-Request-ID`` response header so clients can report it in bug reports.
"""
from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .logging_config import get_logger, request_id_var
from .metrics import METRICS

logger = get_logger("click2go.access")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        token = request_id_var.set(request_id)
        start = time.perf_counter()

        # Prefer the matched route template (e.g. "/plan/{session_id}/status")
        # so metric cardinality stays bounded instead of exploding per-ID.
        route = request.url.path

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000
            METRICS.inc("http_requests_total", {"method": request.method, "status": "500"})
            logger.exception(
                "request failed",
                extra={"method": request.method, "path": route, "duration_ms": round(duration_ms, 2)},
            )
            request_id_var.reset(token)
            raise

        duration_ms = (time.perf_counter() - start) * 1000
        template = _route_template(request, route)
        METRICS.inc(
            "http_requests_total",
            {"method": request.method, "status": str(status_code)},
        )
        METRICS.observe_request(request.method, template, duration_ms)

        response.headers["X-Request-ID"] = request_id
        logger.info(
            "%s %s -> %s (%.1fms)",
            request.method,
            route,
            status_code,
            duration_ms,
            extra={
                "method": request.method,
                "path": route,
                "status": status_code,
                "duration_ms": round(duration_ms, 2),
            },
        )
        request_id_var.reset(token)
        return response


def _route_template(request: Request, fallback: str) -> str:
    """Return the matched route path template to bound metric cardinality."""
    route = request.scope.get("route")
    return getattr(route, "path", fallback)
