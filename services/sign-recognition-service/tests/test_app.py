"""The shared HTTP surface this service must expose, plus the debug REST router.

Two things are pinned here:

* the platform-wide contract (``/healthz``, ``/readyz``, ``/metrics``, ``/``) and the
  documented offline boot — ``uvicorn app.main:app`` must come up with no broker, no
  MLflow and no GPU, which is what makes the service locally runnable at all;
* that a frame posted to the REST router comes back as a contract-valid
  ``SignRecognitionResult``, and that ``/v1/labels`` reports exactly the closed set the
  avatar-pose service can render (the matched-pair guarantee, ADR-0002).
"""

from __future__ import annotations

import base64

from app.api.rest import build_router
from app.config import Settings
from app.pipeline import SignPipeline
from fastapi.testclient import TestClient
from inclusaai_ai_core import create_app
from inclusaai_contracts.events import VideoFrame
from inclusaai_sign_vocab import FINGERSPELL_ALPHABET, phrase_ids


def _app(settings: Settings) -> tuple[SignPipeline, object]:
    pipeline = SignPipeline(settings)
    app = create_app(
        settings, pipeline=pipeline, extra_routers=[build_router(pipeline.engine, settings)]
    )
    return pipeline, app


def test_health_metrics_and_root(settings: Settings) -> None:
    # No pipeline attached -> lifespan starts nothing (no Kafka needed for this test).
    app = create_app(settings)
    with TestClient(app) as client:
        assert client.get("/healthz").status_code == 200
        assert client.get("/readyz").status_code == 200

        metrics = client.get("/metrics")
        assert metrics.status_code == 200
        assert "inference_latency" in metrics.text or "active_sessions" in metrics.text

        assert client.get("/").json()["service"] == settings.service_name


def test_offline_boot_runs_pipeline_lifespan() -> None:
    """The documented ``uvicorn app.main:app`` boot must work with no infra.

    With no broker the pipeline starts OFFLINE — producer/consumers skipped — yet the
    app still boots and readiness flips to ready.
    """
    settings = Settings(
        service_name="sign-offline-boot",
        model_name=None,  # offline stub engine -> no MLflow call
        kafka_bootstrap_servers="",  # offline -> no broker connection attempt
        otel_exporter_otlp_endpoint=None,
    )
    pipeline, app = _app(settings)
    with TestClient(app) as client:  # entering runs the lifespan (pipeline.start)
        assert client.get("/readyz").status_code == 200
        assert client.get("/healthz").status_code == 200
    assert pipeline.producer.online is False  # confirms we took the offline path


def test_recognize_endpoint_returns_contract_valid_result(settings: Settings) -> None:
    """A posted frame classifies against the closed set, not into the void."""
    _, app = _app(settings)
    frame = VideoFrame(
        session_id="s1",
        presenter_id="signer1",
        sequence=0,
        timestamp_ms=1000,
        width=640,
        height=480,
        payload_b64=base64.b64encode(b"frame-bytes").decode(),
    )
    with TestClient(app) as client:
        response = client.post("/v1/recognize", json=frame.model_dump())
    assert response.status_code == 200
    results = response.json()
    assert results, "a decodable frame must classify"
    result = results[0]
    assert result["session_id"] == "s1"
    assert result["signer_id"] == "signer1"
    assert result["label"] in set(phrase_ids()) | set(FINGERSPELL_ALPHABET)


def test_recognize_endpoint_returns_nothing_for_an_empty_frame(settings: Settings) -> None:
    """Empty payload -> no pose -> no phantom recognition (mirrors the pipeline)."""
    _, app = _app(settings)
    frame = VideoFrame(
        session_id="s1",
        presenter_id="signer1",
        sequence=0,
        timestamp_ms=1000,
        width=640,
        height=480,
        payload_b64="",
    )
    with TestClient(app) as client:
        response = client.post("/v1/recognize", json=frame.model_dump())
    assert response.status_code == 200
    assert response.json() == []


def test_labels_endpoint_reports_the_closed_set(settings: Settings) -> None:
    """/v1/labels is the recognizer half of the symmetric-vocabulary contract."""
    _, app = _app(settings)
    with TestClient(app) as client:
        body = client.get("/v1/labels").json()
    assert body["sign_language"] == settings.sign_language
    assert body["phrases"] == list(phrase_ids())
    assert body["fingerspelling"] == list(FINGERSPELL_ALPHABET)
    assert body["gesture_window_frames"] == settings.gesture_window_frames
