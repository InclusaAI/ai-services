"""Readiness honesty gates: REQUIRE_KAFKA / REQUIRE_MODEL -> /readyz 503.

These are the first ai_core tests; they pin the contract that an instance which
is *not* actually serving events reports not-ready instead of a green 200.
"""

from __future__ import annotations

import os
from typing import Any

import httpx
import pytest
from inclusaai_ai_core.config import BaseServiceSettings
from inclusaai_ai_core.pipeline import BaseInferencePipeline
from inclusaai_ai_core.service import create_app


# ---------------------------------------------------------------- fake pipeline
class StubPipeline:
    """Minimal stand-in satisfying the Pipeline protocol + readiness gates."""

    def __init__(self, settings: BaseServiceSettings, *, problems: list[str]) -> None:
        self.settings = settings
        self._problems = problems
        self.start_calls = 0
        self.stop_calls = 0

    async def start(self) -> None:
        self.start_calls += 1

    async def stop(self) -> None:
        self.stop_calls += 1
        raise RuntimeError("does not swallow stop-time cleanup")

    def readiness_problems(self) -> list[str]:
        return self._problems


def _settings(**kw: Any) -> BaseServiceSettings:
    return BaseServiceSettings(service_name="test-svc", env="test", **kw)


def make_app(settings: BaseServiceSettings, *, problems: list[str] | None) -> Any:
    pipeline = None if problems is None else StubPipeline(settings, problems=problems)
    return create_app(settings, pipeline=pipeline)


# --------------------------------------------------------------- readiness gates
def test_no_gates_no_problems() -> None:
    """Defaults: no REQUIRE_* env -> an offline pipeline is still ready (dev mode)."""
    p = BaseInferencePipeline(_settings(), topics=["ai.transcript.segment"])
    assert p.readiness_problems() == []


def test_require_kafka_runs_offline_is_not_ready() -> None:
    env = {
        "KAFKA_BOOTSTRAP_SERVERS": "localhost:1",  # nothing there
        "REQUIRE_KAFKA": "true",
    }
    for k, v in env.items():
        os.environ[k] = v
    try:
        p = BaseInferencePipeline(_settings(), topics=["ai.transcript.segment"])
        # synchronous check of the gate logic without a running loop:
        assert not p.producer.online
        assert "kafka-broker-unreachable" in p.readiness_problems()
    finally:
        for k in env:
            os.environ.pop(k, None)


def test_require_model_flags_unloaded_model() -> None:
    os.environ["REQUIRE_MODEL"] = "true"
    try:
        p = BaseInferencePipeline(_settings(), topics=["ai.transcript.segment"])
        p.model_ready = False
        assert "model-not-loaded" in p.readiness_problems()
        p.model_ready = True
        assert p.readiness_problems() == []
    finally:
        os.environ.pop("REQUIRE_MODEL", None)


def test_gates_off_by_default_even_without_kafka() -> None:
    p = BaseInferencePipeline(_settings(), topics=["ai.transcript.segment"])
    assert p.producer.online is False
    assert p.readiness_problems() == []


# ------------------------------------------------------------------- /readyz HTTP
# httpx's ASGITransport does not run the app lifespan, so these tests drive
# ``app.router.lifespan_context`` manually — the same code path uvicorn runs.


def _lifespan(app: Any) -> Any:
    return app.router.lifespan_context(app)


@pytest.mark.asyncio
async def test_app_not_ready_when_pipeline_has_problems() -> None:
    app = make_app(_settings(), problems=["kafka-broker-unreachable"])
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    async with _lifespan(app), client:
        assert (await client.get("/healthz")).status_code == 200  # liveness stays green
        r = await client.get("/readyz")
        assert r.status_code == 503
        assert r.json() == {"status": "not-ready"}


@pytest.mark.asyncio
async def test_app_ready_when_pipeline_clean() -> None:
    app = make_app(_settings(), problems=[])
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    async with _lifespan(app), client:
        r = await client.get("/readyz")
        assert r.status_code == 200
        assert r.json() == {"status": "ready"}


@pytest.mark.asyncio
async def test_stop_exception_does_not_break_shutdown() -> None:
    """pipeline.stop() raising must not break the lifespan shutdown path."""
    app = make_app(_settings(), problems=[])
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    async with _lifespan(app), client:
        assert (await client.get("/readyz")).status_code == 200
        assert (await client.get("/healthz")).status_code == 200
    # lifespan exited cleanly despite StubPipeline.stop raising RuntimeError.
