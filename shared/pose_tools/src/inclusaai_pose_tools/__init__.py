"""pose-format (.pose) interchange for InclusaAI.

Bridges the ``pose-format`` library's ``Pose`` container to InclusaAI's two
in-house representations:

* the wire contract ``inclusaai_contracts.events.PoseKeypoint`` (x, y, z,
  visibility), and
* the 51-point ``inclusaai_sign_vocab.skeleton.SKELETON`` layout.

This is transport/representation *plumbing* (ADR-0002). It does not encode any
ASL content: glosses, authoritative vocabulary, and learned models remain gated
on the Deaf-community / linguist consultation.

Public API
----------
``skeleton_header``        the shared ``PoseHeader`` for the 51-point skeleton
``keypoints_to_pose``      wire frames → ``Pose``
``pose_to_keypoints``      one ``Pose`` frame → wire keypoints
``frame_count``            number of frames in a ``Pose``
``holistic_to_skeleton``   MediaPipe Holistic ``Pose`` → 51-point ``Pose``
``fake_skeleton_pose``     deterministic placeholder ``Pose`` (offline/tests)
``pose_code`` / ``pose_for_code``   placeholder class-code reduction + inverse
``to_pose_bytes`` / ``read_pose_bytes``   ``.pose`` binary (de)serialization
"""

from __future__ import annotations

from .codes import pose_code, pose_for_code
from .convert import frame_count, keypoints_to_pose, pose_to_keypoints
from .fakes import fake_skeleton_pose
from .header import COMPONENTS, POINT_FORMAT, skeleton_header
from .holistic import (
    HOLISTIC_BODY_SUBSET,
    HOLISTIC_LEFT_HAND,
    HOLISTIC_POSE,
    HOLISTIC_RIGHT_HAND,
    holistic_to_skeleton,
)
from .serialize import read_pose_bytes, to_pose_bytes

__all__ = [
    "COMPONENTS",
    "POINT_FORMAT",
    "skeleton_header",
    "keypoints_to_pose",
    "pose_to_keypoints",
    "frame_count",
    "holistic_to_skeleton",
    "HOLISTIC_POSE",
    "HOLISTIC_LEFT_HAND",
    "HOLISTIC_RIGHT_HAND",
    "HOLISTIC_BODY_SUBSET",
    "fake_skeleton_pose",
    "pose_code",
    "pose_for_code",
    "to_pose_bytes",
    "read_pose_bytes",
]
