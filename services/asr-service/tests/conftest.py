from __future__ import annotations

import base64

import pytest
from app.config import Settings
from inclusaai_contracts.events import AudioChunk


@pytest.fixture
def settings() -> Settings:
    # model_name=None forces the engine's offline stub path — no MLflow, no Kafka,
    # no GPU — so the whole service is testable in CI.
    return Settings(
        service_name="asr-service-test",
        model_name=None,
        otel_exporter_otlp_endpoint=None,
    )


@pytest.fixture
def audio_chunk() -> AudioChunk:
    return AudioChunk(
        session_id="s1",
        speaker_id="spk1",
        sequence=0,
        timestamp_ms=1000,
        payload_b64=base64.b64encode(b"0123456789").decode(),
    )
