"""Postprocessing: assessment -> ``ai.vision.quality.signal`` payload."""

from __future__ import annotations

from inclusaai_contracts.events import VideoFrame, VisionQualitySignal

from app.quality import QualityAssessment


def to_signal(frame: VideoFrame, assessment: QualityAssessment) -> VisionQualitySignal:
    return VisionQualitySignal(
        session_id=frame.session_id,
        presenter_id=frame.presenter_id,
        timestamp_ms=frame.timestamp_ms,
        framing_ok=assessment.framing_ok,
        lighting_ok=assessment.lighting_ok,
        hand_visibility_ok=assessment.hand_visibility_ok,
        signing_pace=assessment.signing_pace,
        recommendation=assessment.recommendation,
    )
