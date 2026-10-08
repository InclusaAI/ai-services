"""Synthetic 51-point skeleton poses for fingerspelling tests (mediapipe-free).

Builds a ``Pose`` on the shared skeleton whose right hand is posed in a specific
ASL manual-alphabet handshape, with the left hand absent (all zeros). The layout
is a simple 2.5D hand model: wrist at the origin, palm length 2
(wrist -> middle mcp), finger segments of length ~1 extending along +y.

The geometry is deliberately engineered so the feature thresholds in
:mod:`app.inference.fingerspelling` resolve each letter unambiguously — these
tests pin the rule logic, not real-world generalization (that is what the
gated MediaPipe smoke test + a learned model are for).
"""

from __future__ import annotations

from inclusaai_contracts.events import PoseKeypoint
from inclusaai_pose_tools import keypoints_to_pose
from inclusaai_sign_vocab import SKELETON
from pose_format import Pose

_WRIST = (0.0, 0.0, 0.0)
_MCP_Y = 2.0
_MCP_X: dict[str, float] = {"index": 0.35, "middle": 0.0, "ring": -0.35, "pinky": -0.7}
_FINGER_ORDER: tuple[str, ...] = ("index", "middle", "ring", "pinky")

_POSE_CORE: dict[str, tuple[float, float, float]] = {
    "nose": (0.0, 4.0, 0.0),
    "left_shoulder": (-1.0, 3.0, 0.0),
    "right_shoulder": (1.0, 3.0, 0.0),
    "left_elbow": (-1.5, 2.0, 0.0),
    "right_elbow": (1.5, 2.0, 0.0),
    "left_wrist": (-2.0, 1.0, 0.0),
    "right_wrist": (2.0, 1.0, 0.0),
    "left_hip": (-1.0, 0.0, 0.0),
    "right_hip": (1.0, 0.0, 0.0),
}

#: Finger posture -> (pip, dip, tip) offsets from the finger MCP.
_FINGER_POSTURES: dict[str, tuple[tuple[float, float, float], ...]] = {
    "extended": ((0.0, 1.0, 0.0), (0.0, 2.0, 0.0), (0.0, 3.0, 0.0)),
    # V: the middle finger splays out to the side while staying extended.
    "extended_spread": ((0.0, 1.0, 0.0), (-0.7, 1.8, 0.0), (-1.5, 2.6, 0.0)),
    "folded": ((0.0, 0.7, 0.0), (0.7, 0.7, 0.0), (0.7, 0.1, 0.0)),
    "bent": ((0.0, 0.7, 0.0), (0.5, 1.35, 0.0), (0.95, 1.15, 0.0)),  # outward C curve
    "bent_in": ((0.0, 0.7, 0.0), (0.8, 0.5, 0.0), (1.05, 0.3, 0.0)),  # F: index to thumb
}

#: Thumb posture -> (cmc, mcp, ip, tip) absolute coordinates.
_THUMB_POSTURES: dict[
    str,
    tuple[tuple[float, float, float], tuple[float, float, float],
          tuple[float, float, float], tuple[float, float, float]],
] = {
    # A-family: thumb folded across the palm toward the index knuckle.
    "across": ((0.9, 0.5, 0.0), (1.2, 0.8, 0.0), (1.0, 1.4, 0.0), (0.7, 1.9, 0.0)),
    # C: thumb curved out to match the open fingers.
    "bent_out": ((0.9, 0.5, 0.0), (1.6, 0.8, 0.0), (2.1, 1.0, 0.0), (2.3, 1.2, 0.0)),
    # F: thumb tip pinches the curled index tip.
    "pinch": ((0.9, 0.5, 0.0), (1.1, 0.8, 0.0), (1.3, 1.4, 0.0), (1.4, 2.0, 0.0)),
    # G: thumb extended along the index finger, pad near its tip.
    "out_parallel": ((0.9, 0.5, 0.0), (1.1, 1.7, 0.0), (0.95, 3.1, 0.0), (0.8, 4.6, 0.0)),
    # L: thumb extended out perpendicular to the index.
    "out_perp": ((0.9, 0.5, 0.0), (1.7, 0.9, 0.0), (2.6, 1.3, 0.0), (3.5, 1.7, 0.0)),
    # Y: thumb extended out to the side, pinky up.
    "out": ((0.9, 0.5, 0.0), (1.7, 0.9, 0.0), (2.3, 1.2, 0.0), (2.8, 1.5, 0.0)),
}

#: The letters the classifier claims to recognize statically, and the synthetic
#: pose that should resolve to each. ``crossed`` adds the R depth-order swap.
LETTERS: dict[str, dict[str, object]] = {
    "a": {"fingers": ("folded", "folded", "folded", "folded"), "thumb": "across"},
    "b": {"fingers": ("extended", "extended", "extended", "extended"), "thumb": "across"},
    "c": {"fingers": ("bent", "bent", "bent", "bent"), "thumb": "bent_out"},
    "d": {"fingers": ("extended", "folded", "folded", "folded"), "thumb": "across"},
    "f": {"fingers": ("bent_in", "extended", "extended", "extended"), "thumb": "pinch"},
    "g": {"fingers": ("extended", "folded", "folded", "folded"), "thumb": "out_parallel"},
    "i": {"fingers": ("folded", "folded", "folded", "extended"), "thumb": "across"},
    "l": {"fingers": ("extended", "folded", "folded", "folded"), "thumb": "out_perp"},
    "r": {
        "fingers": ("extended", "extended", "folded", "folded"),
        "thumb": "across",
        "crossed": True,
    },
    "u": {"fingers": ("extended", "extended", "folded", "folded"), "thumb": "across"},
    "v": {"fingers": ("extended", "extended_spread", "folded", "folded"), "thumb": "across"},
    "w": {"fingers": ("extended", "extended", "extended", "folded"), "thumb": "across"},
    "y": {"fingers": ("folded", "folded", "folded", "extended"), "thumb": "out"},
}


def handshape_pose(letter: str) -> Pose:
    """A one-frame pose whose right hand is posed as the given letter."""
    cfg = LETTERS[letter]
    postures = cfg["fingers"]
    assert isinstance(postures, tuple)
    thumb = cfg["thumb"]
    assert isinstance(thumb, str)
    crossed = bool(cfg.get("crossed", False))

    keypoints: list[PoseKeypoint] = []
    for name in SKELETON:
        if name in _POSE_CORE:
            x, y, z = _POSE_CORE[name]
            keypoints.append(PoseKeypoint(x=x, y=y, z=z, visibility=1.0))
        elif name.startswith("left_hand_"):
            keypoints.append(PoseKeypoint(x=0.0, y=0.0, z=0.0, visibility=0.0))
        elif name.startswith("right_hand_"):
            keypoints.append(
                _right_hand(name[len("right_hand_") :], postures, thumb, crossed)
            )
        else:  # pragma: no cover — defensive; SKELETON only has the above groups
            raise AssertionError(f"unexpected skeleton landmark {name!r}")
    return keypoints_to_pose([keypoints])


def _right_hand(
    suffix: str,
    postures: tuple[str, str, str, str],
    thumb: str,
    crossed: bool,
) -> PoseKeypoint:
    """One right-hand landmark, posed per the letter config."""
    thumb_coords = _THUMB_POSTURES[thumb]
    thumb_joints = ("thumb_cmc", "thumb_mcp", "thumb_ip", "thumb_tip")

    if suffix == "wrist":
        x, y, z = _WRIST
    elif suffix in thumb_joints:
        x, y, z = thumb_coords[thumb_joints.index(suffix)]
    else:
        finger, joint = suffix.rsplit("_", 1)
        base = (_MCP_X[finger], _MCP_Y, 0.0)
        posture = postures[_FINGER_ORDER.index(finger)]
        if joint == "mcp":
            x, y, z = base
            if crossed:
                # R: the index/middle MCPs start with opposite depth order...
                z = 0.3 if finger == "index" else -0.3
        else:
            dx, dy, dz = _FINGER_POSTURES[posture][{"pip": 0, "dip": 1, "tip": 2}[joint]]
            x, y, z = base[0] + dx, base[1] + dy, base[2] + dz
            if crossed and joint == "tip":
                # ...and their tips swap it (R: fingers crossed).
                z = -0.2 if finger == "index" else 0.2
    return PoseKeypoint(x=x, y=y, z=z, visibility=1.0)
