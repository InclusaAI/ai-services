"""Constrained-vocabulary signing library — pose generation side (ADR-0002).

The avatar generates from the closed set defined in :mod:`inclusaai_sign_vocab`, the
SAME vocabulary the sign-recognition service classifies against (symmetric vocabulary).
Out-of-vocabulary content is fingerspelled; empty input yields a neutral resting pose.

Generation produces pose-format :class:`~pose_format.Pose` objects on the shared
51-point ``skeleton_header`` (via :mod:`inclusaai_pose_tools`) — the same container
the sign-recognition service consumes, extending the matched pair from "shared
vocabulary" to "shared representation." The frames can be serialized to ``.pose``
for cross-team interchange (see ``pose-protocol-response.md``).

The pose *coordinates* here are a deterministic **placeholder** for real motion-capture
/ learned-model data (which ADR-0002 gates on a Deaf-community/linguist consultation).
Only the *shape* is meant to be realistic: full-``SKELETON`` keypoints across several
frames — i.e. the highest-bandwidth ``ai.avatar.pose.frame`` payload the platform must
carry (IMPLEMENTATION §5). Motion is seeded by a stable hash of the phrase id (via
``hashlib``, NOT the salted builtin ``hash()``), so a phrase animates identically across
processes and runs.
"""

from __future__ import annotations

import hashlib
import math

from inclusaai_contracts.events import PoseKeypoint
from inclusaai_pose_tools import keypoints_to_pose
from inclusaai_sign_vocab import NUM_KEYPOINTS, PhraseEntry, fingerspell, match
from pose_format import Pose

#: Intermediate: a sequence of per-frame keypoint lists, before wrapping in a Pose.
_Frames = list[list[PoseKeypoint]]

#: Frames emitted per matched phrase / per fingerspelled letter.
FRAMES_PER_SIGN = 8
FRAMES_PER_LETTER = 4

#: Nominal fps baked into the generated Pose metadata. The *emission* cadence is
#: applied later in postprocessing from ``settings.fps``; these placeholder poses
#: are frame-indexed, not wall-clock timed, so this is only container metadata.
DEFAULT_FPS = 30


def _floats(key: str, count: int) -> list[float]:
    """``count`` deterministic floats in [0, 1) derived from a stable hash of ``key``."""
    out: list[float] = []
    material = key.encode()
    counter = 0
    while len(out) < count:
        digest = hashlib.sha256(material + counter.to_bytes(4, "big")).digest()
        out.extend(
            int.from_bytes(digest[i : i + 4], "big") / 0xFFFFFFFF
            for i in range(0, len(digest), 4)
        )
        counter += 1
    return out[:count]


def _clamp(value: float) -> float:
    return min(1.0, max(0.0, value))


def _base_pose(key: str) -> list[tuple[float, float, float]]:
    """A stable per-keypoint (x, y, z) base pose, clustered around frame center."""
    vals = _floats(key, NUM_KEYPOINTS * 3)
    return [
        (
            0.5 + (vals[3 * i] - 0.5) * 0.6,
            0.5 + (vals[3 * i + 1] - 0.5) * 0.6,
            (vals[3 * i + 2] - 0.5) * 0.2,
        )
        for i in range(NUM_KEYPOINTS)
    ]


def _animate(base: list[tuple[float, float, float]], phase: float) -> list[PoseKeypoint]:
    """One frame: each base keypoint nudged by a small per-index sinusoidal offset."""
    frame: list[PoseKeypoint] = []
    for idx, (bx, by, bz) in enumerate(base):
        wobble = 0.04 * math.sin(2 * math.pi * (phase + idx / len(base)))
        frame.append(PoseKeypoint(x=_clamp(bx + wobble), y=_clamp(by - wobble * 0.5), z=bz))
    return frame


def _sign_frames(key: str, num_frames: int) -> _Frames:
    base = _base_pose(key)
    return [_animate(base, f / num_frames) for f in range(num_frames)]


def pose_for(phrase: PhraseEntry) -> Pose:
    """Deterministic placeholder :class:`Pose` for a vocabulary phrase.

    Full-``SKELETON`` keypoints across ``FRAMES_PER_SIGN`` frames, stable per phrase id.
    A stand-in for real motion data — realistic in shape only (see module docstring).
    """
    return keypoints_to_pose(_sign_frames(f"pose:{phrase.id}", FRAMES_PER_SIGN), fps=DEFAULT_FPS)


def fingerspell_poses(text: str) -> Pose | None:
    """A :class:`Pose` spelling out-of-vocabulary ``text`` letter-by-letter (ADR-0002).

    Returns ``None`` when ``text`` yields no fingerspellable letters.
    """
    frames: _Frames = []
    for letter in fingerspell(text):
        base = _base_pose(f"fs:{letter}")
        frames.extend(_animate(base, f / FRAMES_PER_LETTER) for f in range(FRAMES_PER_LETTER))
    if not frames:
        return None
    return keypoints_to_pose(frames, fps=DEFAULT_FPS)


def neutral_pose() -> Pose:
    """A single neutral resting frame (all keypoints centered), for empty input."""
    frame = [PoseKeypoint(x=0.5, y=0.5) for _ in range(NUM_KEYPOINTS)]
    return keypoints_to_pose([frame], fps=DEFAULT_FPS)


def generate(text: str) -> tuple[str | None, Pose]:
    """Map free transcript text to a ``(phrase_id, Pose)``.

    In-vocabulary → the phrase's pose and its id; out-of-vocabulary but non-empty →
    fingerspelled pose; empty/whitespace → a neutral resting pose. ``phrase_id`` is
    ``None`` on the fingerspelling and neutral paths (no closed-set phrase matched).
    """
    phrase = match(text)
    if phrase is not None:
        return phrase.id, pose_for(phrase)
    if text and text.strip():
        spelled = fingerspell_poses(text)
        if spelled is not None:
            return None, spelled
    return None, neutral_pose()
