"""In-process faster-whisper backend (dev/local only).

Selected via ``ASR_WHISPER_SIZE`` (see [config][app.config]). Presents the SAME
``.predict`` calling convention the production MLflow pyfunc model exposes —
``{"audio": <pcm bytes>, "sample_rate": int}`` in, a list of segment dicts out — so
``AsrEngine`` code is identical whether the model is pulled from the registry (prod)
or constructed here (dev). This does real CPU inference and bypasses MLflow entirely.

``faster_whisper`` is imported lazily inside ``__init__`` so importing this module
never requires the package — the root-env type check and the offline boot path both
stay green when it (or its native deps) is absent, mirroring the lazy ``mlflow``/``grpc``
imports elsewhere in the app.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from inclusaai_telemetry import get_logger

log = get_logger(__name__)

TARGET_SAMPLE_RATE = 16000


class WhisperBackend:
    """A faster-whisper model wrapped in the pyfunc ``.predict`` convention."""

    def __init__(
        self,
        model_size: str,
        *,
        device: str = "cpu",
        compute_type: str = "int8",
        language: str | None = None,
    ) -> None:
        from faster_whisper import WhisperModel  # lazy: optional heavy dep

        self._language = language
        self._model = WhisperModel(model_size, device=device, compute_type=compute_type)
        log.info(
            "asr.whisper.loaded",
            size=model_size,
            device=device,
            compute_type=compute_type,
        )

    def predict(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        """Transcribe one PCM buffer.

        ``payload`` = ``{"audio": <pcm_s16le bytes>, "sample_rate": int}``. Audio must be
        mono 16-bit PCM at 16 kHz (the contract default); other rates are rejected here
        rather than silently mis-transcribed (resampling is a follow-up). Returns segments
        as ``{"text", "start", "end", "confidence"}`` with times in **seconds**.
        """
        audio: bytes = payload["audio"]
        sample_rate = int(payload.get("sample_rate", TARGET_SAMPLE_RATE))
        if sample_rate != TARGET_SAMPLE_RATE:
            raise ValueError(
                f"WhisperBackend expects {TARGET_SAMPLE_RATE} Hz mono PCM, got "
                f"{sample_rate} Hz (resampling is not implemented yet)."
            )

        samples = np.frombuffer(audio, dtype=np.int16).astype(np.float32) / 32768.0
        segments, _info = self._model.transcribe(samples, language=self._language)
        return [
            {
                "text": seg.text.strip(),
                "start": float(seg.start),
                "end": float(seg.end),
                "confidence": (
                    round(math.exp(seg.avg_logprob), 4)
                    if seg.avg_logprob is not None
                    else None
                ),
            }
            for seg in segments
        ]
