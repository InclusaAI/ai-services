"""Text-to-speech engine. Deterministic stub until a model is registered.

Note: an alternative to a self-hosted model is a third-party TTS provider behind
this same interface (ADR-0009); usage is metered either way via ai.usage.aggregate.
"""

from __future__ import annotations

from inclusaai_model_loading import ModelNotAvailable, load_model, measure_latency
from inclusaai_telemetry import get_logger

from app.config import Settings

log = get_logger(__name__)


class TtsEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._model: object | None = None
        self._stub = True

    def load(self) -> None:
        if not self.settings.model_name:
            log.warning("tts.stub_mode", reason="no model_name configured")
            return
        try:
            self._model = load_model(
                self.settings.model_name,
                stage=self.settings.model_stage,
                version=self.settings.model_version,
                tracking_uri=self.settings.mlflow_tracking_uri,
            )
            self._stub = False
        except ModelNotAvailable as exc:
            log.error("tts.model_unavailable", error=str(exc))

    def synthesize(self, text: str, *, language: str) -> bytes:
        """Return raw audio bytes for ``text``.

        TODO(codec): the stub returns silent PCM sized to the text length; a real
        model returns encoded audio in ``settings.encoding`` at ``sample_rate``.
        """
        with measure_latency(self.settings.service_name, self.settings.model_name or "stub"):
            if self._stub or self._model is None:
                return b"\x00\x00" * max(1, len(text))
            # TODO(model-integration): self._model.predict({"text": text, "lang": language})
            raise NotImplementedError("Wire TtsEngine.synthesize to the registered model.")
