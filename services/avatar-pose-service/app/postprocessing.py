"""Postprocessing: pose-frame sequence -> ``ai.avatar.pose.frame`` payloads.

This is the highest-frequency, most bandwidth-sensitive schema in the platform
(IMPLEMENTATION §5) — one event per animation frame. Version carefully.
"""

from __future__ import annotations

from inclusaai_contracts.events import AvatarPoseFrame, TranscriptSegment

from app.vocabulary import PoseFrames


def to_frames(
    segment: TranscriptSegment, phrase_id: str | None, frames: PoseFrames, fps: int
) -> list[AvatarPoseFrame]:
    step_ms = int(1000 / fps) if fps else 33
    return [
        AvatarPoseFrame(
            session_id=segment.session_id,
            phrase_id=phrase_id,
            frame_index=i,
            timestamp_ms=segment.start_ms + i * step_ms,
            fps=fps,
            keypoints=keypoints,
        )
        for i, keypoints in enumerate(frames)
    ]
