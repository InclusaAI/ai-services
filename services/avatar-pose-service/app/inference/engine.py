"""Pose generation engine.

Default path is a constrained-vocabulary lookup (ADR-0002). A learned text->pose
model is optional and, when registered, replaces the lookup.
"""

from __future__ import annotations

from inclusaai_model_loading import ModelNotAvailable, load_model, measure_latency
from inclusaai_telemetry import get_logger

from app import vocabulary
from app.config import Settings
from app.vocabulary import PoseFrames

log = get_logger(__name__)


class PoseEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._model: object | None = None

    def load(self) -> None:
        if not self.settings.model_name:
            log.info("avatar.vocabulary_mode", reason="no learned model configured")
            return
        try:
            self._model = load_model(
                self.settings.model_name,
                stage=self.settings.model_stage,
                version=self.settings.model_version,
                tracking_uri=self.settings.mlflow_tracking_uri,
            )
        except ModelNotAvailable as exc:
            log.error("avatar.model_unavailable", error=str(exc))

    def generate(self, text: str) -> tuple[str | None, PoseFrames]:
        with measure_latency(self.settings.service_name, self.settings.model_name or "vocab"):
            if self._model is None:
                return vocabulary.lookup(text)
            # TODO(model-integration): self._model.predict({"text": text}) -> pose frames
            raise NotImplementedError("Wire PoseEngine.generate to the registered model.")
