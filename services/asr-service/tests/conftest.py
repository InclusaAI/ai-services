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
    # pcm_s16le is the format decode_audio passes straight through; the payload is
    # 10 placeholder bytes (the stub keys off length, not content).
    return AudioChunk(
        session_id="s1",
        speaker_id="spk1",
        sequence=0,
        timestamp_ms=1000,
        encoding="pcm_s16le",
        payload_b64=base64.b64encode(b"0123456789").decode(),
    )
