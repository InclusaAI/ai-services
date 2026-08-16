"""FastAPI app factory shared by every service.

``create_app`` builds the HTTP surface every service must expose — ``/healthz``,
``/readyz``, ``/metrics`` (infra CONTRACT.md conventions) — and drives an optional
inference pipeline through the app lifespan (start on boot, drain on shutdown).
Logging and tracing are configured here so a service's ``main.py`` stays a few lines.
"""

from __future__ import annotations

from collections.abc import Iterable
from contextlib import asynccontextmanager
from typing import Protocol, runtime_checkable

from fastapi import APIRouter, FastAPI
from starlette.responses import Response

from inclusaai_ai_core.config import BaseServiceSettings
from inclusaai_ai_core.health import Readiness, health_router
from inclusaai_telemetry import get_logger, render_latest, setup_logging, setup_tracing

log = get_logger(__name__)


@runtime_checkable
class Pipeline(Protocol):
    """Anything with an async start/stop lifecycle (BaseInferencePipeline satisfies this)."""

    async def start(self) -> None: ...
    async def stop(self) -> None: ...


def _metrics_router() -> APIRouter:
    router = APIRouter()

    @router.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        payload, content_type = render_latest()
        return Response(content=payload, media_type=content_type)

    return router


def create_app(
    settings: BaseServiceSettings,
    *,
    readiness: Readiness | None = None,
    pipeline: Pipeline | None = None,
    extra_routers: Iterable[APIRouter] = (),
) -> FastAPI:
    """Build the service's FastAPI app.

    The pipeline (if given) is started when the app comes up and stopped on
    shutdown; readiness flips to ready only after the pipeline has started.
    """
    setup_logging(settings.log_level, settings.service_name)
    ready = readiness or Readiness()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        log.info("service.starting", service=settings.service_name, env=settings.env)
        if pipeline is not None:
            await pipeline.start()
        ready.set_ready(True)
        log.info("service.ready", service=settings.service_name)
        try:
            yield
        finally:
            ready.set_ready(False)
            if pipeline is not None:
                await pipeline.stop()
            log.info("service.stopped", service=settings.service_name)

    app = FastAPI(title=settings.service_name, version="0.0.0", lifespan=lifespan)
    setup_tracing(settings.service_name, settings.otel_exporter_otlp_endpoint, app=app)

    app.include_router(health_router(ready))
    app.include_router(_metrics_router())

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {"service": settings.service_name, "env": settings.env}

    for router in extra_routers:
        app.include_router(router)

    return app


def run(app: FastAPI, settings: BaseServiceSettings) -> None:
    """Convenience entrypoint: serve ``app`` with uvicorn.

    uvicorn is imported lazily so ai_core doesn't hard-depend on the server at
    import time (Docker images typically launch via the ``uvicorn`` CLI instead).
    """
    import uvicorn

    uvicorn.run(app, host=settings.http_host, port=settings.http_port)
