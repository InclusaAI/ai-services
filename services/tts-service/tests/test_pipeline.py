from __future__ import annotations

from inclusaai_contracts import schema_registry
from inclusaai_contracts.events import TranslationResult

from app.config import Settings
from app.inference.engine import TtsEngine
from app.pipeline import TtsPipeline
from app.postprocessing import to_chunk


def test_engine_stub_synthesizes(settings: Settings) -> None:
    engine = TtsEngine(settings)
    engine.load()
    audio = engine.synthesize("hola", language="es")
    assert isinstance(audio, bytes) and audio


def test_to_chunk_is_contract_valid(settings: Settings, translation: TranslationResult) -> None:
    engine = TtsEngine(settings)
    engine.load()
    audio = engine.synthesize(translation.translated_text, language=translation.target_language)
    chunk = to_chunk(translation, audio, sequence=0, sample_rate=24000, encoding="pcm_s16le")
    validated = schema_registry.validate("ai.tts.audio.chunk", chunk.model_dump())
    assert validated.session_id == "s1"
    assert validated.language == "es"


async def test_handle_publishes_when_ungated(
    settings: Settings, translation: TranslationResult, monkeypatch
) -> None:
    pipeline = TtsPipeline(settings)
    pipeline.engine.load()
    published: list[tuple[str, object]] = []

    async def fake_publish(event_key, payload, *, key=None):  # noqa: ANN001, ANN202
        published.append((event_key, payload))

    monkeypatch.setattr(pipeline, "publish", fake_publish)
    await pipeline.handle("ai.translation.result", translation)
    assert published and published[0][0] == "ai.tts.audio.chunk"
