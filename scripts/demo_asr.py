#!/usr/bin/env python
"""End-to-end ASR demo — no Kafka, no MLflow, just the REST API.

Usage:
    1. Start the ASR service with Whisper:
       cd services/asr-service
       ASR_WHISPER_SIZE=base uv run uvicorn app.main:app --port 8080

    2. Run this script from the repo root:
       uv run python scripts/demo_asr.py

    Or pass your own audio file:
       uv run python scripts/demo_asr.py path/to/audio.wav

The script:
  - Generates a 3-second sine-wave test WAV (if no file given)
  - Sends it to POST /v1/transcribe/file
  - Prints the TranscriptSegment results

Also works with the JSON endpoint:
  - POST /v1/transcribe with a base64-encoded AudioChunk
"""

from __future__ import annotations

import base64
import io
import math
import struct
import sys
import wave
from pathlib import Path

import httpx

BASE_URL = "http://localhost:8080"


def generate_test_wav(duration_s: float = 3.0, freq: float = 440.0) -> bytes:
    """Generate a simple sine-wave WAV file in memory (16 kHz mono s16le)."""
    sample_rate = 16000
    num_samples = int(sample_rate * duration_s)
    amplitude = 16000  # quiet enough to not blow out ears, loud enough for Whisper to see

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for i in range(num_samples):
            t = i / sample_rate
            sample = int(amplitude * math.sin(2 * math.pi * freq * t))
            wf.writeframes(struct.pack("<h", sample))

    return buf.getvalue()


def check_health() -> bool:
    """Check if the ASR service is running."""
    try:
        r = httpx.get(f"{BASE_URL}/healthz", timeout=5)
        return r.status_code == 200
    except httpx.ConnectError:
        return False


def transcribe_file(audio_bytes: bytes, filename: str = "test.wav") -> list[dict]:
    """Upload an audio file and get transcripts back."""
    r = httpx.post(
        f"{BASE_URL}/v1/transcribe/file",
        files={"file": (filename, audio_bytes, "audio/wav")},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def transcribe_base64(audio_bytes: bytes, filename: str = "test.wav") -> list[dict]:
    """Send audio via the JSON/base64 endpoint (matches the Kafka contract shape)."""
    chunk = {
        "session_id": "demo-session",
        "speaker_id": "demo-speaker",
        "sequence": 1,
        "timestamp_ms": 0,
        "sample_rate": 16000,
        "encoding": "wav",
        "payload_b64": base64.b64encode(audio_bytes).decode(),
    }
    r = httpx.post(f"{BASE_URL}/v1/transcribe", json=chunk, timeout=30)
    r.raise_for_status()
    return r.json()


def transcribe_pcm(pcm_bytes: bytes) -> list[dict]:
    """Send raw PCM s16le via the JSON endpoint."""
    chunk = {
        "session_id": "demo-session",
        "speaker_id": "demo-speaker",
        "sequence": 1,
        "timestamp_ms": 0,
        "sample_rate": 16000,
        "encoding": "pcm_s16le",
        "payload_b64": base64.b64encode(pcm_bytes).decode(),
    }
    r = httpx.post(f"{BASE_URL}/v1/transcribe", json=chunk, timeout=30)
    r.raise_for_status()
    return r.json()


def print_results(results: list[dict], label: str = "") -> None:
    """Pretty-print transcription results."""
    if label:
        print(f"\n{'='*60}")
        print(f"  {label}")
        print(f"{'='*60}")

    if not results:
        print("  (no segments returned)")
        return

    for seg in results:
        conf = f"{seg['confidence']:.2%}" if seg.get("confidence") else "N/A"
        print(f"  [{seg['start_ms']}ms - {seg['end_ms']}ms] (conf: {conf})")
        print(f"  \"{seg['text']}\"")
        print()


def main() -> None:
    # --- health check ---
    print(f"Checking ASR service at {BASE_URL} ...")
    if not check_health():
        print("\n❌ ASR service is not running!")
        print("   Start it first:")
        print("   cd services/asr-service")
        print("   ASR_WHISPER_SIZE=base uv run uvicorn app.main:app --port 8080")
        sys.exit(1)
    print("✅ Service is healthy\n")

    # --- determine input ---
    if len(sys.argv) > 1:
        audio_path = Path(sys.argv[1])
        if not audio_path.exists():
            print(f"❌ File not found: {audio_path}")
            sys.exit(1)
        audio_bytes = audio_path.read_bytes()
        filename = audio_path.name
        print(f"📄 Using file: {audio_path} ({len(audio_bytes)} bytes)")
    else:
        print("🎵 Generating 3-second sine-wave test WAV ...")
        audio_bytes = generate_test_wav()
        filename = "test.wav"
        print(f"   Generated {len(audio_bytes)} bytes")

    # --- file upload endpoint ---
    results = transcribe_file(audio_bytes, filename)
    print_results(results, "POST /v1/transcribe/file (multipart upload)")

    # --- JSON base64 endpoint (WAV encoding) ---
    results = transcribe_base64(audio_bytes, filename)
    print_results(results, "POST /v1/transcribe (JSON, encoding=wav)")

    # --- JSON base64 endpoint (raw PCM) ---
    # Decode the WAV to raw PCM for this test
    with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
        pcm = wf.readframes(wf.getnframes())
    results = transcribe_pcm(pcm)
    print_results(results, "POST /v1/transcribe (JSON, encoding=pcm_s16le)")

    # --- list supported formats ---
    r = httpx.get(f"{BASE_URL}/v1/formats", timeout=5)
    if r.status_code == 200:
        fmts = r.json()
        print(f"{'='*60}")
        print("  Supported formats")
        print(f"{'='*60}")
        for f in fmts["formats"]:
            print(f"  {f['encoding']:12s} — {f['description']}")
        print()

    print("✅ Demo complete!")


if __name__ == "__main__":
    main()
