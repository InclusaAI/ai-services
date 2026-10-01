"""Postprocessing: synthesized audio -> ``ai.tts.audio.chunk`` payload."""

from __future__ import annotations

import base64

from inclusaai_contracts.events import TranslationResult, TtsAudioChunk
from inclusaai_utils import now_ms


def to_chunk(
    result: TranslationResult, audio: bytes, *, sequence: int, sample_rate: int, encoding: str
) -> TtsAudioChunk:
    return TtsAudioChunk(
        session_id=result.session_id,
        sequence=sequence,
        timestamp_ms=now_ms(),
        sample_rate=sample_rate,
        encoding=encoding,
        language=result.target_language,
        payload_b64=base64.b64encode(audio).decode(),
    )
