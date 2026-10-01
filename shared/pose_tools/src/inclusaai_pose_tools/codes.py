"""Stub classification codes derived from a pose.

The recognition engine's learned model is gated on ADR-0002, so until then it
classifies with a deterministic placeholder: it reduces a ``Pose`` to a single
integer ``code`` and maps that into the closed vocabulary. ``pose_code`` is that
reduction — it lives here (not in the service) so tests can build a pose that
targets a *known* code via ``pose_for_code``, guaranteeing the test helper and
the engine agree by construction.

This is a placeholder feature, not a real classifier: on genuine MediaPipe poses
(coordinates in ~[0, 1]) the reduction collapses toward 0. Real recognition
arrives with the learned model.
"""

from __future__ import annotations

import numpy as np
import numpy.ma as ma
from pose_format import Pose
from pose_format.numpy.pose_body import NumPyPoseBody

from .convert import _dense
from .header import skeleton_header


def pose_code(pose: Pose) -> int:
    """Reduce a pose to a deterministic integer (the placeholder class code)."""
    data = _dense(pose.body.data)
    if data.size == 0:
        return 0
    return int(round(float(data.flat[0])))  # frame 0, person 0, point 0, X


def pose_for_code(code: int, *, num_frames: int = 1, fps: int = 30) -> Pose:
    """Build a pose ``p`` such that ``pose_code(p) == code`` (test helper)."""
    header = skeleton_header()
    n = header.total_points()
    frames = max(1, num_frames)
    data = np.zeros((frames, 1, n, 3), dtype=np.float32)
    data[0, 0, 0, 0] = float(code)
    confidence = np.ones((frames, 1, n), dtype=np.float32)
    body = NumPyPoseBody(fps=float(fps), data=ma.masked_array(data), confidence=confidence)
    return Pose(header, body)
