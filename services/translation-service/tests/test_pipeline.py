from __future__ import annotations

from app.config import Settings
from app.inference.engine import TranslationEngine
from app.pipeline import TranslationPipeline
from app.postprocessing import to_result
from inclusaai_contracts import schema_registry
from inclusaai_contracts.events import (
    AccessibilityChannel,
    AccessibilityPreferenceUpdated,
    SignRecognitionResult,
    TranscriptSegment,
    VisionQualitySignal,
)


def test_engine_stub_translates(settings: Settings) -> None:
    engine = TranslationEngine(settings)
    engine.load()
    out = engine.translate("hello", source="en", target="es")
    assert "hello" in out


def test_to_result_is_contract_valid(settings: Settings, transcript: TranscriptSegment) -> None:
    engine = TranslationEngine(settings)
    engine.load()
    translated = engine.translate(transcript.text, source="en", target="es")
    result = to_result(
        transcript.session_id,
        transcript.segment_id,
        transcript.text,
        translated,
        source="en",
        target="es",
    )
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


def test_pipeline_subscribes_to_both_text_inputs() -> None:
    """Speech AND the recognized-sign leg — the recognizer needs a consumer."""
    pipeline = TranslationPipeline(Settings(service_name="t", kafka_bootstrap_servers=""))
    assert sorted(pipeline._topics) == [
        "ai.sign.recognition.result",
        "ai.transcript.segment",
    ]


# --------------------------------------------- ai.sign.recognition.result (sign leg)
async def test_handle_consumes_sign_recognition(
    settings: Settings, sign_recognition: SignRecognitionResult, monkeypatch
) -> None:
    """The recognizer's output finally has a consumer: gloss -> spoken language."""
    pipeline = TranslationPipeline(settings)
    pipeline.engine.load()
    published: list[tuple[str, object]] = []

    async def fake_publish(event_key, payload, *, key=None):  # noqa: ANN001, ANN202
        published.append((event_key, payload))

    monkeypatch.setattr(pipeline, "publish", fake_publish)
    await pipeline.handle("ai.sign.recognition.result", sign_recognition)
    assert published
    assert {key for key, _ in published} == {"ai.translation.result"}
    result = published[0][1]
    assert result.session_id == "s1"
    # segment_id correlates back to the sign segment it came from
    assert result.segment_id == "sign_1"


async def test_sign_leg_translates_the_gloss_not_the_label(
    settings: Settings, sign_recognition: SignRecognitionResult, monkeypatch
) -> None:
    """"MORNING" (gloss) is the content; "good_morning" is an internal phrase id."""
    pipeline = TranslationPipeline(settings)
    pipeline.engine.load()
    published: list[tuple[str, object]] = []

    async def fake_publish(event_key, payload, *, key=None):  # noqa: ANN001, ANN202
        published.append((event_key, payload))

    monkeypatch.setattr(pipeline, "publish", fake_publish)
    await pipeline.handle("ai.sign.recognition.result", sign_recognition)
    result = published[0][1]
    assert result.source_text == "MORNING"
    assert "MORNING" in result.translated_text
    assert "good_morning" not in result.translated_text


async def test_sign_leg_falls_back_to_label_when_gloss_is_absent(
    settings: Settings, sign_recognition: SignRecognitionResult, monkeypatch
) -> None:
    """A recognition with no gloss still translates rather than emitting nothing."""
    pipeline = TranslationPipeline(settings)
    pipeline.engine.load()
    published: list[tuple[str, object]] = []

    async def fake_publish(event_key, payload, *, key=None):  # noqa: ANN001, ANN202
        published.append((event_key, payload))

    monkeypatch.setattr(pipeline, "publish", fake_publish)
    glossless = sign_recognition.model_copy(update={"gloss": None})
    await pipeline.handle("ai.sign.recognition.result", glossless)
    assert published[0][1].source_text == "good_morning"


async def test_sign_leg_uses_the_gloss_text_language_not_the_sign_language(
    settings: Settings, sign_recognition: SignRecognitionResult, monkeypatch
) -> None:
    """"ASL" is not a text language pair; the MT source is the configured gloss language."""
    pipeline = TranslationPipeline(settings)
    pipeline.engine.load()
    published: list[tuple[str, object]] = []

    async def fake_publish(event_key, payload, *, key=None):  # noqa: ANN001, ANN202
        published.append((event_key, payload))

    monkeypatch.setattr(pipeline, "publish", fake_publish)
    await pipeline.handle("ai.sign.recognition.result", sign_recognition)
    result = published[0][1]
    assert result.source_language == settings.sign_gloss_source_language
    assert result.source_language != sign_recognition.sign_language


async def test_sign_leg_is_still_preference_gated(
    settings: Settings, sign_recognition: SignRecognitionResult, monkeypatch
) -> None:
    """No participant wants translation -> skip the sign leg too, saving the MT work."""
    pipeline = TranslationPipeline(settings)
    pipeline.engine.load()
    published: list[tuple[str, object]] = []

    async def fake_publish(event_key, payload, *, key=None):  # noqa: ANN001, ANN202
        published.append((event_key, payload))

    monkeypatch.setattr(pipeline, "publish", fake_publish)
    pipeline.preferences.update(
        AccessibilityPreferenceUpdated(
            session_id="s1",
            participant_id="p1",
            channels=[AccessibilityChannel.AVATAR],
            updated_at_ms=0,
        )
    )
    await pipeline.handle("ai.sign.recognition.result", sign_recognition)
    assert not published


async def test_unrelated_events_are_ignored(settings: Settings, monkeypatch) -> None:
    pipeline = TranslationPipeline(settings)
    pipeline.engine.load()
    published: list[tuple[str, object]] = []

    async def fake_publish(event_key, payload, *, key=None):  # noqa: ANN001, ANN202
        published.append((event_key, payload))

    monkeypatch.setattr(pipeline, "publish", fake_publish)
    await pipeline.handle(
        "ai.transcript.segment",
        VisionQualitySignal(session_id="s1", presenter_id="spk1", timestamp_ms=0),
    )
    assert not published


# ------------------------------------------------------------- real model paths
def _registered_model(predict):  # builds the fake pyfunc model
    class Registered:
        def __init__(self) -> None:
            self.calls: list[dict] = []
            self._predict = predict

        def predict(self, payload: dict):
            self.calls.append(payload)
            return self._predict(payload)

    return Registered()


def test_registered_model_translates(settings: Settings) -> None:
    """A registered MLflow model satisfying the contract runs real code."""
    engine = TranslationEngine(settings)
    engine.load()
    engine._model = _registered_model(
        lambda payload: {"translation": f"pass-{payload['source']}-{payload['target']}"}
    )
    engine._backend, engine._stub = "mlflow", False
    assert engine.translate("hello", source="en", target="es") == "pass-en-es"
    assert engine._model.calls[0] == {"text": "hello", "source": "en", "target": "es"}
    assert engine.ready


def test_registered_model_contract_violation_is_loud(settings: Settings) -> None:
    """A mispackaged model raises a contract error — never a silent stub output."""
    import pytest as _pytest

    engine = TranslationEngine(settings)
    engine.load()
    engine._model = _registered_model(lambda payload: (_ for _ in ()).throw(TypeError("x")))
    engine._backend, engine._stub = "mlflow", False
    with _pytest.raises(RuntimeError, match="contract"):
        engine.translate("hello", source="en", target="es")


def test_ready_false_when_model_requested_but_failed(settings: Settings) -> None:
    """Stub fallback with a configured model is NOT ready (REQUIRE_MODEL input)."""
    requested = settings.model_copy(update={"model_name": "translation-nllb"})
    engine = TranslationEngine(requested)
    engine.load()
    engine._backend, engine._stub = "stub", True
    assert not engine.ready
    # But with no model requested at all, the stub is the intent -> ready.
    engine2 = TranslationEngine(settings)  # model_name=None in the fixture
    engine2.load()
    assert engine2.ready
