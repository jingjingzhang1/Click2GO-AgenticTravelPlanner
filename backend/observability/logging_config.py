"""
Structured logging
===================
Configures the root logger with either a human-friendly console format or a
machine-readable JSON format (``LOG_FORMAT=json``). Every log record is
automatically enriched with the current request ID via a ``contextvars``
context variable, so logs can be correlated across a single HTTP request
without threading the ID through every function call.
"""
from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone

from ..config import settings

# Request-scoped correlation ID. Set by RequestContextMiddleware.
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

_RESERVED = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys())


class _RequestIdFilter(logging.Filter):
    """Inject the current request ID into every record."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        record.request_id = request_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per line — ready for Loki/ELK/Datadog ingestion."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
            "service": settings.service_name,
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        # Merge any structured extras passed via logger.info(..., extra={...}).
        for key, value in record.__dict__.items():
            if key not in _RESERVED and key not in payload and key != "request_id":
                payload[key] = value

        return json.dumps(payload, default=str, ensure_ascii=False)


class ConsoleFormatter(logging.Formatter):
    """Compact, readable format for local development."""

    def __init__(self) -> None:
        super().__init__(
            fmt="%(asctime)s %(levelname)-7s [%(request_id)s] %(name)s — %(message)s",
            datefmt="%H:%M:%S",
        )


def configure_logging() -> None:
    """Idempotently configure the root logger from settings."""
    root = logging.getLogger()
    root.setLevel(settings.log_level.upper())

    # Replace handlers so re-configuration (e.g. under Uvicorn reload) is clean.
    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(_RequestIdFilter())
    handler.setFormatter(
        JsonFormatter() if settings.log_format.lower() == "json" else ConsoleFormatter()
    )
    root.addHandler(handler)

    # Tame noisy third-party loggers.
    for noisy in ("uvicorn.access", "httpx", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
