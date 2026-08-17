"""The ASR runtime.

Wraps the registered model and turns raw PCM into timed transcription fragments.
Until a real model is promoted through the ADR-0005 evaluation gate (or when no
``model_name`` is configured), the engine runs a deterministic **stub** so the
whole service — Kafka wiring, contracts, health/metrics — is exercisable offline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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
        self._model: Any = None
        self._stub = True

    def load(self) -> None:
        """Load the ASR model. Precedence: local faster-whisper (dev) > MLflow > stub.

        Any failure degrades to the offline stub with a loud log, so the service stays
        bootable — production readiness should treat a configured-but-unloadable model
        as a hard failure, not a silent stub.
        """
        # DEV-ONLY: in-process faster-whisper, bypassing MLflow (see whisper_backend).
        if self.settings.asr_whisper_size:
            try:
                from app.inference.whisper_backend import WhisperBackend

                self._model = WhisperBackend(
                    self.settings.asr_whisper_size,
                    language=self.settings.transcript_language,
                )
                self._stub = False
                log.info("asr.local_whisper", size=self.settings.asr_whisper_size)
            except Exception as exc:  # noqa: BLE001 — degrade to stub, but say why
                log.error("asr.local_whisper_unavailable", error=str(exc))
                self._stub = True
            return

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
        # The model (MLflow pyfunc in prod, WhisperBackend in dev) shares one convention:
        #   .predict({"audio": pcm, "sample_rate": sr}) -> [{"text","start","end","confidence"}]
        # with segment offsets in seconds; translate them to absolute ms via base_ms.
        result = self._model.predict({"audio": pcm, "sample_rate": sample_rate})
        return [
            Transcription(
                text=seg["text"],
                start_ms=base_ms + int(seg["start"] * 1000),
                end_ms=base_ms + int(seg["end"] * 1000),
                confidence=seg.get("confidence"),
                is_final=True,
            )
            for seg in result
        ]
