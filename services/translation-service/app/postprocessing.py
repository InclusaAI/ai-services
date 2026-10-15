"""Postprocessing: translation -> ``ai.translation.result`` payload.

Takes ``session_id``/``segment_id``/``source_text`` rather than a specific input
event, because both ``ai.transcript.segment`` and ``ai.sign.recognition.result`` feed
the translation and neither should be privileged in the output shape.
"""

from __future__ import annotations

from inclusaai_contracts.events import TranslationResult


def to_result(
    session_id: str,
    segment_id: str,
    source_text: str,
    translated_text: str,
    *,
    source: str,
    target: str,
) -> TranslationResult:
    """Build the ``ai.translation.result`` payload.

    ``segment_id`` is carried through from whichever input produced it, so a consumer
    can correlate a translation back to the exact transcript segment or sign segment
    it came from. ``source_text`` is likewise the *upstream* text: the transcript text,
    or the recognized sign's gloss.
    """
    return TranslationResult(
        session_id=session_id,
        segment_id=segment_id,
        source_language=source,
        target_language=target,
        source_text=source_text,
        translated_text=translated_text,
    )
