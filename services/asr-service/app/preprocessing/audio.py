"""Audio preprocessing: transported payload -> raw PCM ready for the model."""

from __future__ import annotations

import base64

from inclusaai_contracts.events import AudioChunk


def decode_audio(chunk: AudioChunk) -> bytes:
    """Decode a transported audio chunk to raw PCM s16le bytes.

    The transport carries the (possibly encoded) audio base64 in ``payload_b64``.
    ``pcm_s16le`` is returned as-is (already the raw PCM the model wants). ``opus``
    decode + resampling from ``chunk.sample_rate`` to the model's ``target_sample_rate``
    is not implemented yet, so it fails loudly rather than feeding the model garbage.
    """
    raw = base64.b64decode(chunk.payload_b64)
    if chunk.encoding == "pcm_s16le":
        return raw
    raise NotImplementedError(
        f"audio encoding {chunk.encoding!r} is not supported yet; send pcm_s16le "
        "(opus decode + resample is a follow-up)."
    )
