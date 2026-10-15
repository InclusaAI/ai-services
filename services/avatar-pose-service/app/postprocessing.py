"""Postprocessing: a pose-format ``Pose`` -> ``ai.avatar.pose.frame`` payloads.

This is the highest-frequency, most bandwidth-sensitive schema in the platform
(IMPLEMENTATION §5) — one event per animation frame. Version carefully.

The wire contract (``AvatarPoseFrame`` / ``PoseKeypoint``) is unchanged: pose-format
is an internal representation only. Each frame of the ``Pose`` is projected back to
the ordered ``PoseKeypoint`` list the schema expects via ``pose_to_keypoints``.

Takes ``session_id``/``start_ms`` rather than a specific input event, because both
``ai.transcript.segment`` and ``ai.translation.result`` drive generation and neither
should be privileged in the frame layout.
"""

from __future__ import annotations

from inclusaai_contracts.events import AvatarPoseFrame
from inclusaai_pose_tools import frame_count, pose_to_keypoints
from pose_format import Pose


def to_frames(
    session_id: str, start_ms: int, phrase_id: str | None, pose: Pose, fps: int
) -> list[AvatarPoseFrame]:
    """Project a generated ``Pose`` onto the per-frame wire payloads.

    ``start_ms`` anchors the animation on the timeline: the segment's own start for a
    transcript, or arrival time for a translation (which carries no timing).

    ``frame_index`` is **per-``start_ms``-anchor**, not per-session — it restarts at 0
    for each generated phrase. The contract carries no segment id, so a client
    distinguishing concurrent phrases groups on ``timestamp_ms``/``phrase_id``.
    """
    step_ms = int(1000 / fps) if fps else 33
    return [
        AvatarPoseFrame(
            session_id=session_id,
            phrase_id=phrase_id,
            frame_index=i,
            timestamp_ms=start_ms + i * step_ms,
            fps=fps,
            keypoints=pose_to_keypoints(pose, i),
        )
        for i in range(frame_count(pose))
    ]
