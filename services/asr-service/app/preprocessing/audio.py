"""Audio preprocessing: transported payload -> raw PCM ready for the model."""

from __future__ import annotations

import base64

from inclusaai_contracts.events import AudioChunk


def decode_audio(chunk: AudioChunk) -> bytes:
    """Decode a transported audio chunk to raw bytes.

    TODO(codec): the placeholder transport carries base64 bytes directly. A real
    implementation should, when ``chunk.encoding == "opus"``, decode to PCM and
    resample from ``chunk.sample_rate`` to the model's ``target_sample_rate``.
    """
    return base64.b64decode(chunk.payload_b64)
