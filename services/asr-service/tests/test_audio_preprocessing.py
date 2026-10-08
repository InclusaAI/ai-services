"""Tests for audio preprocessing: WAV decode, resampling, and the file upload endpoint."""

from __future__ import annotations

import base64
import io
import wave

import pytest
from app.main import app
from app.preprocessing.audio import (
    _float_to_pcm16,
    _resample,
    decode_audio,
    decode_audio_bytes,
    resample_s16le,
)
from fastapi.testclient import TestClient
from inclusaai_contracts.events import AudioChunk

# ---------------------------------------------------------------------------
# WAV generation helper
# ---------------------------------------------------------------------------


def _make_wav(
    *,
    sample_rate: int = 16000,
    channels: int = 1,
    sample_width: int = 2,
    num_samples: int = 1000,
) -> bytes:
    """Generate a valid WAV file in memory (silence)."""
    # Each sample is `sample_width` bytes, and we have `num_samples * channels` total
    bytes_per_sample = sample_width
    frame_bytes = b"\x00" * (num_samples * channels * bytes_per_sample)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(frame_bytes)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# decode_audio_bytes — WAV
# ---------------------------------------------------------------------------


def test_decode_wav_16khz_mono() -> None:
    wav = _make_wav(sample_rate=16000, channels=1)
    pcm = decode_audio_bytes(wav, filename="test.wav")
    # 16kHz mono, 1000 samples → 1000 samples out
    assert len(pcm) == 1000 * 2  # 16-bit = 2 bytes per sample


def test_decode_wav_stereo_resamples_to_mono() -> None:
    wav = _make_wav(sample_rate=16000, channels=2, num_samples=500)
    pcm = decode_audio_bytes(wav, filename="test.wav")
    # stereo 500 frames → mono 500 samples
    assert len(pcm) == 500 * 2


def test_decode_wav_44khz_resamples_to_16khz() -> None:
    wav = _make_wav(sample_rate=44100, channels=1, num_samples=4410)
    pcm = decode_audio_bytes(wav, filename="test.wav")
    # 4410 samples at 44.1kHz → ~1600 samples at 16kHz
    expected = int(4410 * 16000 / 44100)
    assert abs(len(pcm) // 2 - expected) <= 2  # allow ±2 samples for rounding


def test_decode_wav_8bit() -> None:
    wav = _make_wav(sample_rate=16000, channels=1, sample_width=1, num_samples=200)
    pcm = decode_audio_bytes(wav, filename="test.wav")
    assert len(pcm) == 200 * 2  # 8-bit in, 16-bit out


def test_decode_wav_32bit() -> None:
    wav = _make_wav(sample_rate=16000, channels=1, sample_width=4, num_samples=200)
    pcm = decode_audio_bytes(wav, filename="test.wav")
    assert len(pcm) == 200 * 2  # 32-bit in, 16-bit out


# ---------------------------------------------------------------------------
# decode_audio_bytes — format inference
# ---------------------------------------------------------------------------


def test_decode_audio_bytes_unknown_extension_raises() -> None:
    with pytest.raises(ValueError, match="Unsupported file extension"):
        decode_audio_bytes(b"not audio", filename="test.xyz")


def test_decode_audio_bytes_no_extension_defaults_wav() -> None:
    # No extension → treated as WAV → will fail with bad data, not extension error
    with pytest.raises((ValueError, wave.Error)):
        decode_audio_bytes(b"not a wav", filename="audio")


# ---------------------------------------------------------------------------
# decode_audio — pcm_s16le passthrough with resampling
# ---------------------------------------------------------------------------


def test_decode_audio_pcm_s16le_16khz_passthrough() -> None:
    raw = b"\x00\x01\x02\x03"
    chunk = AudioChunk(
        session_id="s1", speaker_id="spk1", sequence=0, timestamp_ms=0,
        encoding="pcm_s16le", payload_b64=base64.b64encode(raw).decode(),
        sample_rate=16000,
    )
    assert decode_audio(chunk) == raw


def test_decode_audio_pcm_s16le_resamples() -> None:
    # 32kHz mono s16le: 3200 samples → 1600 samples at 16kHz
    raw = b"\x00\x00" * 3200
    chunk = AudioChunk(
        session_id="s1", speaker_id="spk1", sequence=0, timestamp_ms=0,
        encoding="pcm_s16le", payload_b64=base64.b64encode(raw).decode(),
        sample_rate=32000,
    )
    pcm = decode_audio(chunk)
    assert len(pcm) // 2 == 1600


# ---------------------------------------------------------------------------
# resampling math
# ---------------------------------------------------------------------------


def test_resample_s16le_public_helper() -> None:
    # 3200 samples at 32 kHz -> 1600 samples at 16 kHz
    raw = b"\x00\x00" * 3200
    out = resample_s16le(raw, 32000, 16000)
    assert len(out) // 2 == 1600
    # identity is a passthrough
    assert resample_s16le(raw, 16000, 16000) is raw


def test_resample_identity() -> None:
    import numpy as np
    audio = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    assert _resample(audio, 16000, 16000) is audio


def test_resample_downsample() -> None:
    import numpy as np
    audio = np.arange(100, dtype=np.float32)
    result = _resample(audio, 100, 50)
    assert len(result) == 50


def test_float_to_pcm16_clips() -> None:
    import numpy as np
    audio = np.array([2.0, -2.0, 0.5], dtype=np.float32)
    pcm = _float_to_pcm16(audio)
    samples = np.frombuffer(pcm, dtype=np.int16)
    assert samples[0] == 32767   # clipped to max
    assert samples[1] == -32767  # clipped to min (int16: -32768..32767; -1.0*32767 = -32767)
    assert samples[2] == 16383   # 0.5 * 32767 ≈ 16383


# ---------------------------------------------------------------------------
# File upload endpoint
# ---------------------------------------------------------------------------


def test_transcribe_file_endpoint() -> None:
    wav = _make_wav(sample_rate=16000, channels=1, num_samples=16000)
    client = TestClient(app)
    r = client.post(
        "/v1/transcribe/file",
        files={"file": ("test.wav", wav, "audio/wav")},
    )
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)


def test_transcribe_file_empty_returns_empty() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/transcribe/file",
        files={"file": ("empty.wav", b"", "audio/wav")},
    )
    assert r.status_code == 200
    assert r.json() == []


def test_formats_endpoint() -> None:
    client = TestClient(app)
    r = client.get("/v1/formats")
    assert r.status_code == 200
    data = r.json()
    assert "formats" in data
    encodings = [f["encoding"] for f in data["formats"]]
    assert "wav" in encodings
    assert "pcm_s16le" in encodings
