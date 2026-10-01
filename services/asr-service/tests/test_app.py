"""The shared HTTP surface every service must expose builds and responds."""

from __future__ import annotations

from app.config import Settings
from app.pipeline import AsrPipeline
from fastapi.testclient import TestClient
from inclusaai_ai_core import create_app


def test_health_metrics_and_root(settings: Settings) -> None:
    # No pipeline attached -> lifespan starts nothing (no Kafka needed for this test).
    app = create_app(settings)
    with TestClient(app) as client:
        assert client.get("/healthz").status_code == 200
        assert client.get("/readyz").status_code == 200  # ready once lifespan runs

        metrics = client.get("/metrics")
        assert metrics.status_code == 200
        assert "inference_latency" in metrics.text or "active_sessions" in metrics.text

        assert client.get("/").json()["service"] == settings.service_name


def test_offline_boot_runs_pipeline_lifespan() -> None:
    """The documented ``uvicorn app.main:app`` boot must work with no infra.

    With no broker configured the pipeline starts OFFLINE — producer/consumers are
    skipped — yet the app still boots and readiness flips to ready. Guards the
    README Quickstart promise ("no model/Kafka/GPU needed to boot").
    """
    settings = Settings(
        model_name=None,  # stub engine -> no MLflow call
        kafka_bootstrap_servers="",  # offline -> no broker connection attempt
        otel_exporter_otlp_endpoint=None,
    )
    pipeline = AsrPipeline(settings)
    app = create_app(settings, pipeline=pipeline)
    with TestClient(app) as client:  # entering the context runs the lifespan (pipeline.start)
        assert client.get("/readyz").status_code == 200
        assert client.get("/healthz").status_code == 200
    assert pipeline.producer.online is False  # confirms we took the offline path
