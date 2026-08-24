"""Canonical skeletal keypoint layout shared by generation and recognition.

Both avatar-pose (which emits ``PoseKeypoint``s) and sign-recognition (which will
extract MediaPipe landmarks) must agree on WHICH joints exist and in WHAT order —
otherwise a generated pose and an observed pose can never be lined up. This module
owns that single ordered layout as **names/order only** (no coordinates — those are
the avatar service's concern), so this library stays dependency-free.

The layout is a signing-relevant subset of MediaPipe Holistic: an upper-body pose
core plus a full 21-landmark hand per side (MediaPipe Hands topology).
"""

from __future__ import annotations

# Upper-body pose landmarks (subset of MediaPipe Pose) relevant to signing.
_POSE: tuple[str, ...] = (
    "nose",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_hip",
    "right_hip",
)

# One hand = 21 landmarks (MediaPipe Hands topology).
_HAND_LANDMARKS: tuple[str, ...] = (
    "wrist",
    "thumb_cmc",
    "thumb_mcp",
    "thumb_ip",
    "thumb_tip",
    "index_mcp",
    "index_pip",
    "index_dip",
    "index_tip",
    "middle_mcp",
    "middle_pip",
    "middle_dip",
    "middle_tip",
    "ring_mcp",
    "ring_pip",
    "ring_dip",
    "ring_tip",
    "pinky_mcp",
    "pinky_pip",
    "pinky_dip",
    "pinky_tip",
)


def _hand(side: str) -> tuple[str, ...]:
    return tuple(f"{side}_hand_{name}" for name in _HAND_LANDMARKS)


#: Ordered canonical joint names. Keypoint ``i`` in a pose frame corresponds to
#: ``SKELETON[i]``. Pose core first, then the left hand, then the right hand.
SKELETON: tuple[str, ...] = _POSE + _hand("left") + _hand("right")

#: Number of keypoints in every pose frame (pose core + both hands). 51 here.
NUM_KEYPOINTS: int = len(SKELETON)
