"""Deterministic fake skeleton poses (mediapipe-free).

Used for offline-boot degradation (when MediaPipe is unavailable, extraction
falls back to one of these + a loud log) and for tests. Deliberately does NOT
use ``pose_format.utils.generic.fake_holistic_pose`` — that pulls in mediapipe.
"""

from __future__ import annotations

import numpy as np
import numpy.ma as ma
from pose_format import Pose
from pose_format.numpy.pose_body import NumPyPoseBody

from .header import skeleton_header


def fake_skeleton_pose(num_frames: int, *, seed: int, fps: int = 30) -> Pose:
    """A deterministic random pose on the shared header (same seed → same pose)."""
    header = skeleton_header()
    n = header.total_points()
    frames = max(1, num_frames)
    rng = np.random.default_rng(seed)
    data = rng.standard_normal((frames, 1, n, 3)).astype(np.float32)
    confidence = np.ones((frames, 1, n), dtype=np.float32)
    body = NumPyPoseBody(fps=float(fps), data=ma.masked_array(data), confidence=confidence)
    return Pose(header, body)
