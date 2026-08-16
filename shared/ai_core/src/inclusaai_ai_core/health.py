"""Liveness/readiness endpoints (``/healthz``, ``/readyz``).

Endpoint names follow the convention inclusaai-infra's CONTRACT.md is expected to
mandate (see repo README "Missing docs").
"""

from __future__ import annotations

from fastapi import APIRouter
from starlette.responses import JSONResponse


class Readiness:
    """Mutable readiness flag, flipped true once the pipeline is up."""

    def __init__(self) -> None:
        self.ready = False

    def set_ready(self, value: bool = True) -> None:
        self.ready = value


def health_router(readiness: Readiness) -> APIRouter:
    router = APIRouter()

    @router.get("/healthz", include_in_schema=False)
    def healthz() -> dict[str, str]:
        # Liveness: process is up and serving.
        return {"status": "ok"}

    @router.get("/readyz", include_in_schema=False)
    def readyz() -> JSONResponse:
        # Readiness: model loaded + Kafka connected (pipeline started).
        if readiness.ready:
            return JSONResponse({"status": "ready"})
        return JSONResponse({"status": "not-ready"}, status_code=503)

    return router
