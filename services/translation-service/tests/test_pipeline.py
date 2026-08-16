from __future__ import annotations

from inclusaai_contracts import schema_registry
from inclusaai_contracts.events import TranscriptSegment

from app.config import Settings
from app.inference.engine import TranslationEngine
from app.pipeline import TranslationPipeline
from app.postprocessing import to_result


def test_engine_stub_translates(settings: Settings) -> None:
    engine = TranslationEngine(settings)
    engine.load()
    out = engine.translate("hello", source="en", target="es")
    assert "hello" in out


def test_to_result_is_contract_valid(settings: Settings, transcript: TranscriptSegment) -> None:
    engine = TranslationEngine(settings)
    engine.load()
    translated = engine.translate(transcript.text, source="en", target="es")
    result = to_result(transcript, translated, source="en", target="es")
    validated = schema_registry.validate("ai.translation.result", result.model_dump())
    assert validated.session_id == "s1"
    assert validated.target_language == "es"


async def test_handle_publishes_when_ungated(
    settings: Settings, transcript: TranscriptSegment, monkeypatch
) -> None:
    pipeline = TranslationPipeline(settings)
    pipeline.engine.load()
    published: list[tuple[str, object]] = []

    async def fake_publish(event_key, payload, *, key=None):  # noqa: ANN001, ANN202
        published.append((event_key, payload))

    monkeypatch.setattr(pipeline, "publish", fake_publish)
    # No preferences known -> fail open -> should generate.
    await pipeline.handle("ai.transcript.segment", transcript)
    assert published and published[0][0] == "ai.translation.result"
