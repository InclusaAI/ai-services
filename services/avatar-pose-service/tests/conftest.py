from __future__ import annotations

import pytest
from app.config import Settings
from inclusaai_contracts.events import TranscriptSegment, TranslationResult


@pytest.fixture
def settings() -> Settings:
    return Settings(
        service_name="avatar-pose-test",
        model_name=None,
        otel_exporter_otlp_endpoint=None,
    )


@pytest.fixture
def transcript() -> TranscriptSegment:
    return TranscriptSegment(
        session_id="s1",
        speaker_id="spk1",
        segment_id="seg_1",
        text="hello there",
        start_ms=0,
        end_ms=1000,
        language="en",
    )


@pytest.fixture
def translation() -> TranslationResult:
    """The Deaf-presenter leg: recognized sign gloss, translated into a spoken language.

    ``translated_text`` is what the avatar signs; ``source_text`` must not be used.
    """
    return TranslationResult(
        session_id="s1",
        segment_id="seg_1",
        source_language="ASL",
        target_language="en",
        source_text="HELLO",
        translated_text="hello",
    )
