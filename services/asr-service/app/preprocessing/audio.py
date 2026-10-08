"""Audio preprocessing: transported payload -> raw PCM ready for the model.

Supports multiple input formats:
- ``pcm_s16le``: raw 16-bit signed little-endian PCM (passthrough)
- ``wav``: WAV files (stdlib ``wave`` module)
- ``mp3``: MP3 files (requires ``pydub`` + ``ffmpeg``)
- ``ogg``: OGG/Opus files (requires ``pydub`` + ``ffmpeg``)

All formats are resampled to 16 kHz mono s16le before being returned, which is
what faster-whisper expects.
"""

from __future__ import annotations

import base64
import io
import wave

import numpy as np
from inclusaai_contracts.events import AudioChunk

_TARGET_SAMPLE_RATE = 16000


def decode_audio(chunk: AudioChunk) -> bytes:
    """Decode a transported audio chunk to 16 kHz mono PCM s16le bytes."""
    raw = base64.b64decode(chunk.payload_b64)
    encoding = chunk.encoding.lower()

    if encoding == "pcm_s16le":
        return _resample_pcm(raw, chunk.sample_rate)

    if encoding == "wav":
        return _decode_wav(raw)

    # pydub handles mp3, ogg, opus, flac, and many more
    if encoding in ("mp3", "ogg", "opus", "flac", "m4a", "webm"):
        return _decode_pydub(raw, encoding)

    raise NotImplementedError(
        f"audio encoding {encoding!r} is not supported. "
        f"Supported: pcm_s16le, wav, mp3, ogg, opus, flac, m4a, webm."
    )


def decode_audio_bytes(data: bytes, *, filename: str = "audio.wav") -> bytes:
    """Decode raw audio file bytes to 16 kHz mono PCM s16le.

    Infers format from the filename extension. Used by the file-upload endpoint.
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "wav"

    format_map = {
        "wav": "wav",
        "mp3": "mp3",
        "ogg": "ogg",
        "opus": "opus",
        "flac": "flac",
        "m4a": "m4a",
        "webm": "webm",
    }

    encoding = format_map.get(ext)
    if encoding is None:
        raise ValueError(
            f"Unsupported file extension '.{ext}'. "
            f"Supported: {', '.join(sorted(format_map))}"
        )

    if encoding == "wav":
        return _decode_wav(data)
    return _decode_pydub(data, encoding)


# ---------------------------------------------------------------------------
# Internal decoders
# ---------------------------------------------------------------------------


def _decode_wav(data: bytes) -> bytes:
    """Decode a WAV buffer to 16 kHz mono s16le PCM."""
    with wave.open(io.BytesIO(data), "rb") as wf:
        channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        sample_rate = wf.getframerate()
        frames = wf.readframes(wf.getnframes())

    # Convert to numpy for resampling
    if sample_width == 1:
        audio = np.frombuffer(frames, dtype=np.uint8).astype(np.float32) - 128.0
    elif sample_width == 2:
        audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32)
    elif sample_width == 4:
        audio = np.frombuffer(frames, dtype=np.int32).astype(np.float32) / 65536.0
    else:
        raise ValueError(f"Unsupported WAV sample width: {sample_width} bytes")

    # Mix to mono if stereo
    if channels == 2:
        audio = audio.reshape(-1, 2).mean(axis=1)
    elif channels > 2:
        audio = audio.reshape(-1, channels).mean(axis=1)

    # Resample to 16 kHz
    audio = _resample(audio, sample_rate, _TARGET_SAMPLE_RATE)

    # Convert to int16
    return _float_to_pcm16(audio)


def _decode_pydub(data: bytes, format: str) -> bytes:
    """Decode mp3/ogg/opus/etc via pydub to 16 kHz mono s16le PCM."""
    try:
        from pydub import AudioSegment  # lazy import
    except ImportError as exc:
        raise RuntimeError(
            f"Decoding {format} requires pydub. Install it: pip install pydub"
        ) from exc

    segment = AudioSegment.from_io(io.BytesIO(data), format=format)
    # Convert to mono, 16 kHz, 16-bit
    segment = segment.set_channels(1).set_frame_rate(_TARGET_SAMPLE_RATE).set_sample_width(2)
    return segment.raw_data


def _resample_pcm(data: bytes, source_rate: int) -> bytes:
    """Resample raw s16le PCM from source_rate to 16 kHz."""
    if source_rate == _TARGET_SAMPLE_RATE:
        return data

    audio = np.frombuffer(data, dtype=np.int16).astype(np.float32)
    audio = _resample(audio, source_rate, _TARGET_SAMPLE_RATE)
    return _float_to_pcm16(audio)


def resample_s16le(pcm: bytes, src_rate: int, dst_rate: int) -> bytes:
    """Resample raw s16le PCM from ``src_rate`` to ``dst_rate`` (linear interp).

    Public so the whisper backend can apply the same convention when called
    directly with a non-16 kHz buffer (the decode path already resamples).
    """
    if src_rate == dst_rate:
        return pcm
    audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
    audio = _resample(audio, src_rate, dst_rate)
    return _float_to_pcm16(audio)


def _resample(audio: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    """Simple linear-interpolation resampling. Good enough for ASR preprocessing."""
    if src_rate == dst_rate:
        return audio
    duration = len(audio) / src_rate
    num_out = int(duration * dst_rate)
    x_old = np.linspace(0, duration, len(audio), endpoint=False)
    x_new = np.linspace(0, duration, num_out, endpoint=False)
    return np.interp(x_new, x_old, audio).astype(np.float32)


def _float_to_pcm16(audio: np.ndarray) -> bytes:
    """Convert float32 audio (range ~[-1, 1]) to s16le bytes, clipped."""
    clipped = np.clip(audio, -1.0, 1.0)
    return (clipped * 32767).astype(np.int16).tobytes()
