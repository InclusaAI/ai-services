"""The ASR runtime.

Wraps the registered model and turns raw PCM into timed transcription fragments.
Until a real model is promoted through the ADR-0005 evaluation gate (or when no
``model_name`` is configured), the engine runs a deterministic **stub** so the
whole service — Kafka wiring, contracts, health/metrics — is exercisable offline.
"""

from __future__ import annotations

from dataclasses import dataclass

from inclusaai_model_loading import ModelNotAvailable, measure_latency
from inclusaai_telemetry import get_logger

from app.config import Settings
from app.models.loader import load_asr_model

log = get_logger(__name__)


@dataclass
class Transcription:
    """One recognized fragment (pre-contract; postprocessing maps it to the event)."""

    text: str
    start_ms: int
    end_ms: int
    confidence: float | None = None
    is_final: bool = True


class AsrEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._model: object | None = None
        self._stub = True

    def load(self) -> None:
        """Pull the registered model. Stays in stub mode if none is configured/available."""
        if not self.settings.model_name:
            log.warning("asr.stub_mode", reason="no model_name configured")
            self._stub = True
            return
        try:
            self._model = load_asr_model(self.settings)
            self._stub = False
        except ModelNotAvailable as exc:
            # Keep dev bootable, but log loudly — production readiness should treat
            # a promoted-but-unloadable model as a hard failure, not a silent stub.
            log.error("asr.model_unavailable", error=str(exc))
            self._stub = True

    def transcribe(self, pcm: bytes, *, sample_rate: int, base_ms: int) -> list[Transcription]:
        model_label = self.settings.model_name or "stub"
        with measure_latency(self.settings.service_name, model_label):
            if self._stub or self._model is None:
                return self._transcribe_stub(pcm, base_ms)
            return self._transcribe_model(pcm, sample_rate=sample_rate, base_ms=base_ms)

    def _transcribe_stub(self, pcm: bytes, base_ms: int) -> list[Transcription]:
        return [
            Transcription(
                text=f"[stub transcript: {len(pcm)} audio bytes]",
                start_ms=base_ms,
                end_ms=base_ms + 1000,
                confidence=None,
                is_final=True,
            )
        ]

    def _transcribe_model(
        self, pcm: bytes, *, sample_rate: int, base_ms: int
    ) -> list[Transcription]:
        # TODO(model-integration): map to the registered model's pyfunc signature, e.g.
        #   result = self._model.predict({"audio": pcm, "sample_rate": sample_rate})
        # then translate segment offsets into absolute ms using base_ms.
        raise NotImplementedError(
            "Wire _transcribe_model to the registered ASR model's pyfunc signature."
        )
