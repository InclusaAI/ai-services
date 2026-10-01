"""Prometheus metrics primitives (web-framework-agnostic).

Includes the model latency histogram used for the per-model benchmarks the quality
bar asks for (ai-services-IMPLEMENTATION.md §8), and event throughput counters.
The ``/metrics`` HTTP route is mounted by ``inclusaai_ai_core`` (which owns the web
layer); here we only expose the metric objects and a renderer.

Scaling-signal gauges (active sessions, queue depth) for the autoscaler (ADR-0008)
live in ``inclusaai_ai_core.scaling``.
"""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

# Per-model inference latency — also mirrored to MLflow by model_loading.benchmark.
INFERENCE_LATENCY = Histogram(
    "inference_latency_seconds",
    "Model inference latency in seconds",
    labelnames=("service", "model"),
)
EVENTS_CONSUMED = Counter(
    "events_consumed_total",
    "Kafka events consumed",
    labelnames=("service", "event_key"),
)
EVENTS_PUBLISHED = Counter(
    "events_published_total",
    "Kafka events published",
    labelnames=("service", "event_key"),
)
INFERENCE_ERRORS = Counter(
    "inference_errors_total",
    "Inference errors",
    labelnames=("service",),
)


def render_latest() -> tuple[bytes, str]:
    """Return (payload, content_type) for a Prometheus scrape."""
    return generate_latest(), CONTENT_TYPE_LATEST
