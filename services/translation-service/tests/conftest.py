from __future__ import annotations

import pytest
from app.config import Settings
from inclusaai_contracts.events import SignRecognitionResult, TranscriptSegment


@pytest.fixture
def settings() -> Settings:
    return Settings(
        service_name="translation-test",
        model_name=None,
        otel_exporter_otlp_endpoint=None,
    )


@pytest.fixture
def transcript() -> TranscriptSegment:
    return TranscriptSegment(
        session_id="s1",
        speaker_id="spk1",
        segment_id="seg_1",
        text="hello world",
        start_ms=0,
        end_ms=1000,
        language="en",
    )


@pytest.fixture
def sign_recognition() -> SignRecognitionResult:
    """The Deaf-presenter leg's input: a recognized closed-set ASL phrase."""
    return SignRecognitionResult(
        session_id="s1",
        signer_id="signer1",
        segment_id="sign_1",
        label="good_morning",
        gloss="MORNING",
        is_fingerspelling=False,
        start_ms=1000,
        end_ms=1400,
        sign_language="ASL",
    )
