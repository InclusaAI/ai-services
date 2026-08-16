from __future__ import annotations

import pytest
from app.config import Settings
from inclusaai_contracts.events import TranslationResult


@pytest.fixture
def settings() -> Settings:
    return Settings(
        service_name="tts-test",
        model_name=None,
        otel_exporter_otlp_endpoint=None,
    )


@pytest.fixture
def translation() -> TranslationResult:
    return TranslationResult(
        session_id="s1",
        segment_id="seg_1",
        source_language="en",
        target_language="es",
        source_text="hello world",
        translated_text="hola mundo",
    )
