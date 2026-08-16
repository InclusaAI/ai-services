"""Translation engine. Deterministic stub until a model is registered."""

from __future__ import annotations

from inclusaai_model_loading import ModelNotAvailable, load_model, measure_latency
from inclusaai_telemetry import get_logger

from app.config import Settings

log = get_logger(__name__)


class TranslationEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._model: object | None = None
        self._stub = True

    def load(self) -> None:
        if not self.settings.model_name:
            log.warning("translation.stub_mode", reason="no model_name configured")
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
            log.error("translation.model_unavailable", error=str(exc))

    def translate(self, text: str, *, source: str, target: str) -> str:
        with measure_latency(self.settings.service_name, self.settings.model_name or "stub"):
            if self._stub or self._model is None:
                return f"[{target}] {text}"
            # TODO(model-integration): self._model.predict({"text": text, "src": source, "tgt": target})
            raise NotImplementedError("Wire TranslationEngine.translate to the registered model.")
