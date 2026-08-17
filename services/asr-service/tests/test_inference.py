"""Engine model-path mapping + audio decode, offline (no model download).

The always-on tests here are the durable regression guard for the real ASR wiring:
they exercise ``_transcribe_model`` with a fake pyfunc-shaped model (no faster-whisper,
no download) and the ``decode_audio`` contract. The real faster-whisper backend is
smoke-tested only when ``ASR_RUN_WHISPER_TESTS=1`` (it downloads a ~145 MB model), so
CI never reaches for the network.
"""

from __future__ import annotations

import base64
import os

import pytest
from app.config import Settings
from app.inference.engine import AsrEngine
from app.preprocessing.audio import decode_audio
from inclusaai_contracts.events import AudioChunk


class _FakeModel:
    """Stands in for the MLflow pyfunc / WhisperBackend — same .predict convention."""

    def predict(self, payload: dict) -> list[dict]:
        assert isinstance(payload["audio"], bytes)
        assert payload["sample_rate"] == 16000
        # Offsets in SECONDS, as both backends return.
        return [
            {"text": "hello", "start": 0.0, "end": 0.5, "confidence": 0.9},
            {"text": "world", "start": 0.5, "end": 1.2, "confidence": 0.8},
        ]


def test_transcribe_model_maps_segments(settings: Settings) -> None:
    engine = AsrEngine(settings)
    engine._model = _FakeModel()  # noqa: SLF001 — wiring a fake backend for the test
    engine._stub = False

    out = engine.transcribe(b"pcmpcmpcm", sample_rate=16000, base_ms=1000)

    assert [t.text for t in out] == ["hello", "world"]
    # seconds -> absolute ms via base_ms (1000).
    assert (out[0].start_ms, out[0].end_ms) == (1000, 1500)
    assert (out[1].start_ms, out[1].end_ms) == (1500, 2200)
    assert out[0].confidence == 0.9
    assert all(t.is_final for t in out)


def _chunk(encoding: str, raw: bytes) -> AudioChunk:
    return AudioChunk(
        session_id="s1",
        speaker_id="spk1",
        sequence=0,
        timestamp_ms=0,
        encoding=encoding,
        payload_b64=base64.b64encode(raw).decode(),
    )


def test_decode_audio_pcm_passthrough() -> None:
    assert decode_audio(_chunk("pcm_s16le", b"\x00\x01\x02\x03")) == b"\x00\x01\x02\x03"


def test_decode_audio_opus_raises() -> None:
    with pytest.raises(NotImplementedError):
        decode_audio(_chunk("opus", b"\x00\x01"))


@pytest.mark.skipif(
    os.getenv("ASR_RUN_WHISPER_TESTS") != "1",
    reason="set ASR_RUN_WHISPER_TESTS=1 to exercise real faster-whisper (downloads a model)",
)
def test_whisper_backend_smoke() -> None:
    import numpy as np
    from app.inference.whisper_backend import WhisperBackend

    backend = WhisperBackend("base")
    # 1 s of silence, 16 kHz mono pcm_s16le — asserts a well-formed result, not content.
    pcm = np.zeros(16000, dtype=np.int16).tobytes()
    out = backend.predict({"audio": pcm, "sample_rate": 16000})

    assert isinstance(out, list)
    for seg in out:
        assert {"text", "start", "end", "confidence"} <= set(seg)
