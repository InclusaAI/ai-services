"""Observability primitives shared by every inference service:
structured logging, Prometheus metrics, OpenTelemetry tracing.
"""

from inclusaai_telemetry.logging import get_logger, setup_logging
from inclusaai_telemetry.metrics import (
    EVENTS_CONSUMED,
    EVENTS_PUBLISHED,
    INFERENCE_ERRORS,
    INFERENCE_LATENCY,
    render_latest,
)
from inclusaai_telemetry.tracing import setup_tracing

__all__ = [
    "setup_logging",
    "get_logger",
    "setup_tracing",
    "render_latest",
    "INFERENCE_LATENCY",
    "EVENTS_CONSUMED",
    "EVENTS_PUBLISHED",
    "INFERENCE_ERRORS",
]
