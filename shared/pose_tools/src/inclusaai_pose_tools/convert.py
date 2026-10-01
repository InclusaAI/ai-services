"""Convert between the ``PoseKeypoint`` wire contract and pose-format ``Pose``.

``inclusaai_contracts.events.PoseKeypoint`` is the on-the-wire landmark shape
(``{x, y, z, visibility}``, ordered by ``SKELETON``). Internally the services
work with pose-format ``Pose`` objects (one shared ``skeleton_header``). These
helpers move between the two without touching the wire contract itself.

pose-format layout: ``body.data`` has shape ``(frames, people, points, 3)`` and
``body.confidence`` has shape ``(frames, people, points)``. We always use a
single person (index 0).
"""

from __future__ import annotations

import numpy as np
import numpy.ma as ma
from inclusaai_contracts.events import PoseKeypoint
from pose_format import Pose
from pose_format.numpy.pose_body import NumPyPoseBody

from .header import skeleton_header


def _dense(arr) -> np.ndarray:
    """Underlying ndarray of a (possibly masked) pose-format array.

    We read the *underlying* data rather than filling masked entries with zero.
    pose-format masks any point whose confidence is 0 (``NumPyPoseBody.__init__``),
    but our wire contract carries ``visibility`` separately — so we keep the
    coordinates and let ``visibility`` signal confidence. This makes
    ``keypoints_to_pose`` ∘ ``pose_to_keypoints`` exact for every point,
    including low/zero-confidence ones, and it survives a ``.pose`` round-trip
    (``write`` stores ``data.data``; ``read`` keeps it under the mask).
    """
    return ma.getdata(arr)


def frame_count(pose: Pose) -> int:
    """Number of frames in a pose."""
    data = pose.body.data
    return int(data.shape[0]) if getattr(data, "ndim", 0) else 0


def keypoints_to_pose(frames: list[list[PoseKeypoint]], fps: int = 30) -> Pose:
    """Build a single-person ``Pose`` (on the shared header) from wire frames."""
    header = skeleton_header()
    n = header.total_points()
    num_frames = max(1, len(frames))
    data = np.zeros((num_frames, 1, n, 3), dtype=np.float32)
    confidence = np.zeros((num_frames, 1, n), dtype=np.float32)
    for f, keypoints in enumerate(frames):
        for i, kp in enumerate(keypoints[:n]):
            data[f, 0, i, 0] = kp.x
            data[f, 0, i, 1] = kp.y
            data[f, 0, i, 2] = kp.z
            confidence[f, 0, i] = kp.visibility
    body = NumPyPoseBody(fps=float(fps), data=ma.masked_array(data), confidence=confidence)
    return Pose(header, body)


def pose_to_keypoints(pose: Pose, frame_index: int) -> list[PoseKeypoint]:
    """Extract one frame of a pose as an ordered ``PoseKeypoint`` list."""
    data = _dense(pose.body.data)
    confidence = _dense(pose.body.confidence)
    n = data.shape[2]
    keypoints: list[PoseKeypoint] = []
    for i in range(n):
        x, y, z = (float(v) for v in data[frame_index, 0, i, :3])
        visibility = float(confidence[frame_index, 0, i]) if confidence.size else 1.0
        keypoints.append(PoseKeypoint(x=x, y=y, z=z, visibility=visibility))
    return keypoints
