"""Postprocessing: engine output -> ``ai.transcript.segment`` contract payload."""

from __future__ import annotations

from inclusaai_contracts.events import AudioChunk, TranscriptSegment
from inclusaai_utils import new_id

from app.inference.engine import Transcription


def to_segment(chunk: AudioChunk, transcription: Transcription, language: str) -> TranscriptSegment:
    """Assemble a contract-valid TranscriptSegment from a transcription + its source chunk."""
    return TranscriptSegment(
        session_id=chunk.session_id,
        speaker_id=chunk.speaker_id,
        segment_id=new_id("seg"),
        text=transcription.text,
        start_ms=transcription.start_ms,
        end_ms=transcription.end_ms,
        language=language,
        is_final=transcription.is_final,
        confidence=transcription.confidence,
    )
