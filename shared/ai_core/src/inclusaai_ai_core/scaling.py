"""Scaling-signal gauges for the GPU autoscaler (ADR-0008).

The autoscaler keys off active concurrent sessions and queue depth, so services
must export these as first-class signals — not treat them as free.
"""

from __future__ import annotations

from prometheus_client import Gauge

ACTIVE_SESSIONS = Gauge(
    "active_sessions",
    "Number of sessions this service currently has in-flight work for",
    labelnames=("service",),
)
QUEUE_DEPTH = Gauge(
    "queue_depth",
    "Pending items awaiting inference in this service",
    labelnames=("service",),
)


def set_active_sessions(service: str, count: int) -> None:
    ACTIVE_SESSIONS.labels(service).set(count)


def set_queue_depth(service: str, depth: int) -> None:
    QUEUE_DEPTH.labels(service).set(depth)
