from __future__ import annotations

from app.config import Settings
from app.inference.engine import TranslationEngine
from app.pipeline import TranslationPipeline
from app.postprocessing import to_result
from inclusaai_contracts import schema_registry
from inclusaai_contracts.events import TranscriptSegment


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
