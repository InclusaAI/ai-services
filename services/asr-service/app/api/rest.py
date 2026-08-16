"""Service-specific REST routes (health/metrics come from ai_core).

Exposes a synchronous debug endpoint that runs the same engine + postprocessing
the Kafka pipeline uses, so you can exercise the model without a broker.
"""

from __future__ import annotations

from fastapi import APIRouter

from inclusaai_contracts.events import AudioChunk, TranscriptSegment

from app.config import Settings
from app.inference.engine import AsrEngine
from app.postprocessing.segments import to_segment
from app.preprocessing.audio import decode_audio


def build_router(engine: AsrEngine, settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/v1", tags=["asr"])

    @router.post("/transcribe", response_model=list[TranscriptSegment])
    def transcribe(chunk: AudioChunk) -> list[TranscriptSegment]:
        """Transcribe one audio chunk synchronously (debug/eval; bypasses Kafka)."""
        pcm = decode_audio(chunk)
        results = engine.transcribe(pcm, sample_rate=chunk.sample_rate, base_ms=chunk.timestamp_ms)
        return [to_segment(chunk, t, settings.transcript_language) for t in results]

    return router
