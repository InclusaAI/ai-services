"""Reconcile MediaPipe Holistic poses with InclusaAI's 51-point sign skeleton.

MediaPipe Holistic (as loaded by pose-format) produces ~543 points across the
components ``POSE_LANDMARKS`` (33), ``FACE_LANDMARKS`` (468),
``LEFT_HAND_LANDMARKS`` (21), ``RIGHT_HAND_LANDMARKS`` (21), and
``POSE_WORLD_LANDMARKS`` (33). Our wire skeleton keeps only 9 upper-body pose
points plus both 21-point hands = 51; the face is dropped.

``holistic_to_skeleton`` performs that selection with pose-format's own
``Pose.get_components`` — which reorders components to the requested order and
permutes each component's points to the requested order — so the 51 output
points come out in ``SKELETON`` order. The result is then rebuilt on the shared
``skeleton_header`` so every InclusaAI pose carries one identical header.

This module is mediapipe-free: it only names MediaPipe's components and points
as string constants and operates on an already-built holistic ``Pose``.
MediaPipe itself lives in the sign-recognition service (behind a guarded import).
"""

from __future__ import annotations

from pose_format import Pose
from pose_format.numpy.pose_body import NumPyPoseBody

from .header import skeleton_header

#: MediaPipe Holistic component names we keep (face + world are dropped).
HOLISTIC_POSE = "POSE_LANDMARKS"
HOLISTIC_LEFT_HAND = "LEFT_HAND_LANDMARKS"
HOLISTIC_RIGHT_HAND = "RIGHT_HAND_LANDMARKS"

#: The 9 MediaPipe ``PoseLandmark`` names we keep, in SKELETON body order.
#: (nose, shoulders, elbows, wrists, hips — upper body, no face/legs/feet.)
HOLISTIC_BODY_SUBSET = [
    "NOSE",
    "LEFT_SHOULDER",
    "RIGHT_SHOULDER",
    "LEFT_ELBOW",
    "RIGHT_ELBOW",
    "LEFT_WRIST",
    "RIGHT_WRIST",
    "LEFT_HIP",
    "RIGHT_HIP",
]


def holistic_to_skeleton(holistic: Pose) -> Pose:
    """Subset a MediaPipe Holistic pose to the 51-point sign skeleton."""
    selected = holistic.get_components(
        [HOLISTIC_POSE, HOLISTIC_LEFT_HAND, HOLISTIC_RIGHT_HAND],
        {HOLISTIC_POSE: HOLISTIC_BODY_SUBSET},
    )
    header = skeleton_header()
    dims = selected.body.data.shape[-1]
    if dims != header.num_dims():
        raise ValueError(
            f"holistic pose has {dims} spatial dims, expected {header.num_dims()} "
            "(is it XYZC / did the loader change format?)"
        )
    # Rebuild on the shared header so downstream code sees one identical schema.
    body = NumPyPoseBody(
        fps=selected.body.fps,
        data=selected.body.data,
        confidence=selected.body.confidence,
    )
    return Pose(header, body)
