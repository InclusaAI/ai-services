"""Postprocessing: translation -> ``ai.translation.result`` payload."""

from __future__ import annotations

from inclusaai_contracts.events import TranscriptSegment, TranslationResult


def to_result(
    segment: TranscriptSegment, translated_text: str, *, source: str, target: str
) -> TranslationResult:
    return TranslationResult(
        session_id=segment.session_id,
        segment_id=segment.segment_id,
        source_language=source,
        target_language=target,
        source_text=segment.text,
        translated_text=translated_text,
    )
