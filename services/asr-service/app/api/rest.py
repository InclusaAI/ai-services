"""Service-specific REST routes (health/metrics come from ai_core).

Exposes:
- ``POST /v1/transcribe``      — JSON body with base64 audio (contract-shaped)
- ``POST /v1/transcribe/file`` — multipart file upload (any common audio format)
- ``GET  /v1/formats``         — list supported audio formats
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, UploadFile
from inclusaai_contracts.events import AudioChunk, TranscriptSegment

from app.config import Settings
from app.inference.engine import AsrEngine
from app.postprocessing.segments import to_segment
from app.preprocessing.audio import decode_audio, decode_audio_bytes


def build_router(engine: AsrEngine, settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/v1", tags=["asr"])

    @router.post("/transcribe", response_model=list[TranscriptSegment])
    def transcribe(chunk: AudioChunk) -> list[TranscriptSegment]:
        """Transcribe one audio chunk (JSON body with base64 payload).

        The ``encoding`` field determines the decoder:
        ``pcm_s16le``, ``wav``, ``mp3``, ``ogg``, ``opus``, ``flac``.
        All formats are resampled to 16 kHz mono before transcription.
        """
        pcm = decode_audio(chunk)
        results = engine.transcribe(pcm, sample_rate=16000, base_ms=chunk.timestamp_ms)
        return [to_segment(chunk, t, settings.transcript_language) for t in results]

    @router.post("/transcribe/file", response_model=list[TranscriptSegment])
    async def transcribe_file(
        file: Annotated[
            UploadFile, File(description="Audio file (WAV, MP3, OGG, FLAC, etc.)")
        ],
        session_id: str = "file-upload",
        speaker_id: str = "uploader",
    ) -> list[TranscriptSegment]:
        """Transcribe an uploaded audio file.

        Accepts any common audio format. The filename extension is used to
        determine the format (e.g. ``recording.wav``, ``speech.mp3``).
        Returns the same ``TranscriptSegment`` contract as the JSON endpoint.
        """
        filename = file.filename or "audio.wav"
        data = await file.read()
        if not data:
            return []

        pcm = decode_audio_bytes(data, filename=filename)
        from inclusaai_utils import now_ms

        chunk = AudioChunk(
            session_id=session_id,
            speaker_id=speaker_id,
            sequence=0,
            timestamp_ms=now_ms(),
            sample_rate=16000,
            encoding="pcm_s16le",
            payload_b64="",  # not needed — we already decoded
        )
        # Override: we already have PCM, call engine directly
        results = engine.transcribe(pcm, sample_rate=16000, base_ms=chunk.timestamp_ms)
        return [to_segment(chunk, t, settings.transcript_language) for t in results]

    @router.get("/formats")
    def supported_formats() -> dict[str, object]:
        """List supported audio input formats."""
        return {
            "formats": [
                {"encoding": "pcm_s16le", "description": "Raw 16-bit signed little-endian PCM"},
                {"encoding": "wav", "description": "WAV (any sample rate, mono or stereo)"},
                {"encoding": "mp3", "description": "MP3 (requires pydub + ffmpeg)"},
                {"encoding": "ogg", "description": "OGG Vorbis (requires pydub + ffmpeg)"},
                {"encoding": "opus", "description": "Opus (requires pydub + ffmpeg)"},
                {"encoding": "flac", "description": "FLAC (requires pydub + ffmpeg)"},
                {"encoding": "m4a", "description": "M4A/AAC (requires pydub + ffmpeg)"},
                {"encoding": "webm", "description": "WebM audio (requires pydub + ffmpeg)"},
            ],
            "target_sample_rate": 16000,
            "target_channels": 1,
            "target_bit_depth": 16,
        }

    return router
