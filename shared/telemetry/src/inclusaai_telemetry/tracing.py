"""OpenTelemetry tracing setup (OTLP exporter).

FastAPI auto-instrumentation is applied only if the optional
``opentelemetry-instrumentation-fastapi`` package is installed, so the core
dependency set stays small and the service still boots without it.
"""

from __future__ import annotations

from typing import Any

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def setup_tracing(
    service_name: str,
    otlp_endpoint: str | None = None,
    app: Any | None = None,
) -> None:
    """Install a global tracer provider exporting to an OTLP collector.

    If ``otlp_endpoint`` is falsy, tracing is left as a no-op (safe for local runs
    without a collector). If ``app`` is a FastAPI instance and the instrumentation
    package is present, HTTP spans are captured automatically.
    """
    if not otlp_endpoint:
        return

    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint)))
    trace.set_tracer_provider(provider)

    if app is not None:
        try:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

            FastAPIInstrumentor.instrument_app(app)
        except Exception:  # noqa: BLE001 — instrumentation is best-effort/optional
            pass
