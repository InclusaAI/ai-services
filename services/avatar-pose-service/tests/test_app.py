"""The shared HTTP surface this service must expose, plus the debug REST router.

Two things are pinned here:

* the platform-wide contract (``/healthz``, ``/readyz``, ``/metrics``, ``/``) and the
  documented offline boot — ``uvicorn app.main:app`` must come up with no broker, no
  MLflow and no GPU, which is what makes the service locally runnable at all;
* that text posted to the REST router comes back as contract-valid
  ``AvatarPoseFrame`` payloads, and that ``/v1/vocabulary`` reports exactly the closed
  set the sign-recognition service classifies against (matched-pair guarantee,
  ADR-0002).
"""

from __future__ import annotations

from app.api.rest import build_router
from app.config import Settings
from app.pipeline import AvatarPosePipeline
from fastapi.testclient import TestClient
from inclusaai_ai_core import create_app
from inclusaai_sign_vocab import FINGERSPELL_ALPHABET, phrase_ids


def _app(settings: Settings) -> tuple[AvatarPosePipeline, object]:
    pipeline = AvatarPosePipeline(settings)
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
        service_name="avatar-offline-boot",
        model_name=None,  # vocabulary mode -> no MLflow call
        kafka_bootstrap_servers="",  # offline -> no broker connection attempt
        otel_exporter_otlp_endpoint=None,
    )
    pipeline, app = _app(settings)
    with TestClient(app) as client:  # entering runs the lifespan (pipeline.start)
        assert client.get("/readyz").status_code == 200
        assert client.get("/healthz").status_code == 200
    assert pipeline.producer.online is False  # confirms we took the offline path


def test_pose_endpoint_returns_contract_valid_frames(settings: Settings) -> None:
    _, app = _app(settings)
    with TestClient(app) as client:
        response = client.post(
            "/v1/pose", json={"text": "hello there", "session_id": "s1", "start_ms": 0}
        )
    assert response.status_code == 200
    frames = response.json()
    assert frames
    assert frames[0]["phrase_id"] == "hello"  # in-vocabulary -> closed-set phrase
    assert [f["frame_index"] for f in frames] == list(range(len(frames)))
    assert all(len(f["keypoints"]) > 0 for f in frames)


def test_pose_endpoint_fingerspells_out_of_vocabulary_text(settings: Settings) -> None:
    _, app = _app(settings)
    with TestClient(app) as client:
        frames = client.post("/v1/pose", json={"text": "zzz"}).json()
    assert frames  # still produces a pose, just with no closed-set phrase
    assert frames[0]["phrase_id"] is None


def test_pose_endpoint_anchors_on_the_requested_start_ms(settings: Settings) -> None:
    """The REST path has no source timing, so an explicit anchor must be honoured."""
    _, app = _app(settings)
    with TestClient(app) as client:
        frames = client.post("/v1/pose", json={"text": "hello", "start_ms": 5000}).json()
    assert frames[0]["timestamp_ms"] == 5000
    assert frames[1]["timestamp_ms"] > frames[0]["timestamp_ms"]


def test_vocabulary_endpoint_reports_the_closed_set(settings: Settings) -> None:
    """/v1/vocabulary is the generator half of the symmetric-vocabulary contract."""
    _, app = _app(settings)
    with TestClient(app) as client:
        body = client.get("/v1/vocabulary").json()
    assert body["phrase_count"] == len(phrase_ids())
    assert [entry["id"] for entry in body["phrases"]] == list(phrase_ids())
    assert body["fingerspelling"] == list(FINGERSPELL_ALPHABET)


def test_documented_example_request_actually_works(settings: Settings) -> None:
    """The example in the OpenAPI schema must be a working request.

    Guards against the docs drifting into something that only *looks* like a valid
    call: "Try it out" in /docs sends exactly this body.
    """
    _, app = _app(settings)
    content = app.openapi()["paths"]["/v1/pose"]["post"]["requestBody"]["content"][
        "application/json"
    ]
    # The docs must actually carry an example, or "Try it out" sends an empty stub.
    assert "examples" in content, "OpenAPI request body has no example to prefill"
    example = content["examples"][0]
    assert example["text"], "example must carry text to sign"
    with TestClient(app) as client:
        response = client.post("/v1/pose", json=example)
    assert response.status_code == 200
    frames = response.json()
    assert frames and frames[0]["phrase_id"] == "hello"
    assert frames[0]["session_id"] == example["session_id"]
    assert frames[0]["timestamp_ms"] == example["start_ms"]
