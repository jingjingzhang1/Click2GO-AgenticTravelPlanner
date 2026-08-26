"""
Observability package
=====================
Cross-cutting concerns: structured logging, request-scoped context
(request IDs), latency middleware, and lightweight in-process metrics.
"""
from .logging_config import configure_logging, get_logger, request_id_var
from .metrics import METRICS, render_prometheus
from .middleware import RequestContextMiddleware

__all__ = [
    "configure_logging",
    "get_logger",
    "request_id_var",
    "METRICS",
    "render_prometheus",
    "RequestContextMiddleware",
]
