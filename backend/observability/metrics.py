"""
Lightweight in-process metrics
==============================
A dependency-free counter/histogram registry that exposes a Prometheus text
exposition endpoint at ``/metrics``. Deliberately tiny — swap for
``prometheus_client`` if you need multiprocess or richer metric types, but
this keeps the demo self-contained with zero extra dependencies.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Dict, Tuple


class _Metrics:
    """Thread-safe counters and latency accumulators keyed by label tuples."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: Dict[Tuple[str, Tuple[Tuple[str, str], ...]], float] = defaultdict(float)
        self._latency_sum: Dict[Tuple[str, str], float] = defaultdict(float)
        self._latency_count: Dict[Tuple[str, str], int] = defaultdict(int)
        self._started_at = time.time()

    def inc(self, name: str, labels: Dict[str, str] | None = None, value: float = 1.0) -> None:
        key = (name, tuple(sorted((labels or {}).items())))
        with self._lock:
            self._counters[key] += value

    def observe_request(self, method: str, path: str, duration_ms: float) -> None:
        key = (method, path)
        with self._lock:
            self._latency_sum[key] += duration_ms
            self._latency_count[key] += 1

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "uptime_seconds": round(time.time() - self._started_at, 1),
                "counters": {
                    f"{name}{_fmt_labels(labels)}": val
                    for (name, labels), val in self._counters.items()
                },
                "avg_latency_ms": {
                    f"{m} {p}": round(self._latency_sum[(m, p)] / self._latency_count[(m, p)], 2)
                    for (m, p) in self._latency_count
                },
            }


def _fmt_labels(labels: Tuple[Tuple[str, str], ...]) -> str:
    if not labels:
        return ""
    inner = ",".join(f'{k}="{v}"' for k, v in labels)
    return "{" + inner + "}"


METRICS = _Metrics()


def render_prometheus() -> str:
    """Render the current metrics in Prometheus text exposition format."""
    snap = METRICS.snapshot()
    lines = [
        "# HELP click2go_uptime_seconds Process uptime in seconds.",
        "# TYPE click2go_uptime_seconds gauge",
        f"click2go_uptime_seconds {snap['uptime_seconds']}",
        "# HELP click2go_http_requests_total Total HTTP requests by method/path/status.",
        "# TYPE click2go_http_requests_total counter",
    ]
    for series, value in snap["counters"].items():
        lines.append(f"click2go_{series} {value}")
    lines.append("# HELP click2go_http_request_latency_ms Average request latency by route.")
    lines.append("# TYPE click2go_http_request_latency_ms gauge")
    for series, value in snap["avg_latency_ms"].items():
        method, path = series.split(" ", 1)
        lines.append(
            f'click2go_http_request_latency_ms{{method="{method}",path="{path}"}} {value}'
        )
    return "\n".join(lines) + "\n"
