"""Postprocessing: recognition -> ``ai.sign.recognition.result`` payload."""

from __future__ import annotations

from inclusaai_contracts.events import SignRecognitionResult, VideoFrame
from inclusaai_utils import new_id

from app.inference.engine import Recognition


def to_result(
    frame: VideoFrame,
    recognition: Recognition,
    sign_language: str,
    *,
    start_ms: int | None = None,
    end_ms: int | None = None,
) -> SignRecognitionResult:
    """Build the contract payload for one recognition.

    A windowed recognition spans the window's first-to-last frame timestamps;
    a single-frame recognition (default) spans just that frame.
    """
    return SignRecognitionResult(
        session_id=frame.session_id,
        signer_id=frame.presenter_id,
        segment_id=new_id("sign"),
        label=recognition.label,
        gloss=recognition.gloss,
        is_fingerspelling=recognition.is_fingerspelling,
        start_ms=start_ms or frame.timestamp_ms,
        end_ms=end_ms or frame.timestamp_ms,
        confidence=recognition.confidence,
        sign_language=sign_language,
    )
