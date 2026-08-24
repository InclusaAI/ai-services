"""Postprocessing: a pose-format ``Pose`` -> ``ai.avatar.pose.frame`` payloads.

This is the highest-frequency, most bandwidth-sensitive schema in the platform
(IMPLEMENTATION §5) — one event per animation frame. Version carefully.

The wire contract (``AvatarPoseFrame`` / ``PoseKeypoint``) is unchanged: pose-format
is an internal representation only. Each frame of the ``Pose`` is projected back to
the ordered ``PoseKeypoint`` list the schema expects via ``pose_to_keypoints``.
"""

from __future__ import annotations

from inclusaai_contracts.events import AvatarPoseFrame, TranscriptSegment
from inclusaai_pose_tools import frame_count, pose_to_keypoints
from pose_format import Pose


def to_frames(
    segment: TranscriptSegment, phrase_id: str | None, pose: Pose, fps: int
) -> list[AvatarPoseFrame]:
    step_ms = int(1000 / fps) if fps else 33
    return [
        AvatarPoseFrame(
            session_id=segment.session_id,
            phrase_id=phrase_id,
            frame_index=i,
            timestamp_ms=segment.start_ms + i * step_ms,
            fps=fps,
            keypoints=pose_to_keypoints(pose, i),
        )
        for i in range(frame_count(pose))
    ]
