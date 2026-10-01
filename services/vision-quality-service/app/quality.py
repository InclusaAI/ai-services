"""Presenter video-quality assessment (framing / lighting / hand visibility / pace).

Feeds presenter-assist so a signer/speaker can be nudged to improve their setup.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class QualityAssessment:
    framing_ok: bool | None = None
    lighting_ok: bool | None = None
    hand_visibility_ok: bool | None = None
    signing_pace: str | None = None  # "slow" | "ok" | "fast"
    recommendation: str | None = None


def assess(image_bytes: bytes) -> QualityAssessment:
    """Assess one frame.

    TODO(vision): real checks via MediaPipe/opencv — face centering (framing),
    brightness histogram (lighting), hand landmark presence (hand visibility), and
    inter-sign timing (pace). The placeholder returns a neutral OK assessment.
    """
    if not image_bytes:
        return QualityAssessment(recommendation="no frame received")
    return QualityAssessment(
        framing_ok=True,
        lighting_ok=True,
        hand_visibility_ok=True,
        signing_pace="ok",
    )
