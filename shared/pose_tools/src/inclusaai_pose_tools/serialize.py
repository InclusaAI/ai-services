""".pose binary (de)serialization — thin wrappers over pose-format's own IO.

The ``.pose`` format is a compact binary container with a JavaScript reader
(``pose-format`` ships ``pose-viewer`` / an npm package), which makes it a
concrete cross-team interchange option: the frontend can read the same bytes the
Python services write. See ``pose-protocol-response.md``.
"""

from __future__ import annotations

import io

from pose_format import Pose


def to_pose_bytes(pose: Pose) -> bytes:
    """Serialize a pose to ``.pose`` bytes."""
    buffer = io.BytesIO()
    pose.write(buffer)
    return buffer.getvalue()


def read_pose_bytes(data: bytes) -> Pose:
    """Read a pose from ``.pose`` bytes."""
    return Pose.read(data)
