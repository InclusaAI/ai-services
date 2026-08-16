"""Sign recognition engine: landmark sequences -> closed-set label (+ fingerspelling).

Recognizes against the SAME constrained vocabulary the avatar generates from
(symmetric vocabulary, ADR-0002), with fingerspelling as the fallback for
out-of-vocabulary content. Runs a deterministic stub until a model is registered.
"""

from __future__ import annotations

from dataclasses import dataclass

from inclusaai_model_loading import ModelNotAvailable, load_model, measure_latency
from inclusaai_telemetry import get_logger

from app.config import Settings
from app.detection import Landmarks

log = get_logger(__name__)

# TODO(vocab): load the real closed set (~150-300 phrases) shared with avatar-pose.
SAMPLE_VOCAB = ["hello", "thank-you", "yes", "no"]


@dataclass
class Recognition:
    label: str
    gloss: str | None
    is_fingerspelling: bool
    confidence: float | None = None


class SignEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._model: object | None = None
        self._stub = True

    def load(self) -> None:
        if not self.settings.model_name:
            log.warning("sign.stub_mode", reason="no model_name configured")
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
            log.error("sign.model_unavailable", error=str(exc))

    def recognize(self, landmarks: Landmarks) -> list[Recognition]:
        """Classify a landmark observation. Returns [] when nothing is recognized.

        TODO(model): production buffers frames into temporal gesture windows before
        classifying, rather than emitting per frame.
        """
        if not landmarks:
            return []
        with measure_latency(self.settings.service_name, self.settings.model_name or "stub"):
            if self._stub or self._model is None:
                label = SAMPLE_VOCAB[int(landmarks[0]) % len(SAMPLE_VOCAB)]
                return [Recognition(label=label, gloss=label, is_fingerspelling=False)]
            # TODO(model-integration): self._model.predict(landmark_window)
            raise NotImplementedError("Wire SignEngine.recognize to the registered model.")
