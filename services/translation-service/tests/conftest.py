from __future__ import annotations

import pytest
from app.config import Settings
from inclusaai_contracts.events import TranscriptSegment


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
