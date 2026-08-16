"""Vision-quality engine: heuristic assessment by default, optional learned model."""

from __future__ import annotations

from inclusaai_model_loading import ModelNotAvailable, load_model, measure_latency
from inclusaai_telemetry import get_logger

from app import quality
from app.config import Settings
from app.quality import QualityAssessment

log = get_logger(__name__)


class VisionQualityEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._model: object | None = None

    def load(self) -> None:
        if not self.settings.model_name:
            log.info("vision.heuristic_mode", reason="no learned model configured")
            return
        try:
            self._model = load_model(
                self.settings.model_name,
                stage=self.settings.model_stage,
                version=self.settings.model_version,
                tracking_uri=self.settings.mlflow_tracking_uri,
            )
        except ModelNotAvailable as exc:
            log.error("vision.model_unavailable", error=str(exc))

    def assess(self, image_bytes: bytes) -> QualityAssessment:
        with measure_latency(self.settings.service_name, self.settings.model_name or "heuristic"):
            if self._model is None:
                return quality.assess(image_bytes)
            # TODO(model-integration): self._model.predict(image) -> QualityAssessment
            raise NotImplementedError("Wire VisionQualityEngine.assess to the registered model.")
