"""Rule-based ASL fingerspelling classifier — model-free, runs offline.

Reads one frame of the shared 51-point skeleton (pose core + full 21-landmark
hands, per ``inclusaai_sign_vocab.skeleton``) and classifies the signer's
dominant handshape against the ASL manual alphabet — the bounded ~26-symbol
fallback ADR-0002 scopes for out-of-vocabulary content.

Deterministic and heuristic: it derives per-finger curl (a joint-extension
ratio) and thumb-placement features purely from landmark geometry and matches
them against the static handshapes of the alphabet. No MLflow model, no
training data, and NOT gated on the ADR-0002 dataset consultation — this is
geometry, not learned content.

Coverage is honest about the alphabet's motion- and orientation-dependent
letters:

* classified statically: ``a b c d f g i l r u v w y``
* NOT classified (``None``, caller falls back): ``e``/``o``/``x`` (their
  shapes sit too close to ``a``/``c`` for 2.5D geometry to resolve
  reliably), ``h`` (same static shape as ``u`` — only palm orientation
  differs), ``j``/``z`` (motion), ``k``/``m``/``n``/``p``/``q`` (palm
  orientation or fingertip geometry too subtle), and ``s``/``t`` (share
  ``a``'s fist; returned as ``a``).

``classify_handshape`` returns ``None`` when no usable hand is detected or no
rule fires — the caller (``SignEngine``) decides the fallback (the closed-set
phrase stub).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from inclusaai_pose_tools import pose_to_keypoints
from inclusaai_sign_vocab import SKELETON
from pose_format import Pose

#: Landmark name -> position in the ordered skeleton.
_INDEX: dict[str, int] = {name: i for i, name in enumerate(SKELETON)}

#: Finger -> (mcp, pip, dip, tip) landmark-name suffixes within one hand.
_FINGER_JOINTS: dict[str, tuple[str, str, str, str]] = {
    "index": ("index_mcp", "index_pip", "index_dip", "index_tip"),
    "middle": ("middle_mcp", "middle_pip", "middle_dip", "middle_tip"),
    "ring": ("ring_mcp", "ring_pip", "ring_dip", "ring_tip"),
    "pinky": ("pinky_mcp", "pinky_pip", "pinky_dip", "pinky_tip"),
}
_THUMB_JOINTS: tuple[str, str, str, str] = ("thumb_cmc", "thumb_mcp", "thumb_ip", "thumb_tip")

_HAND_NAMES: tuple[str, ...] = (
    "wrist",
    *_THUMB_JOINTS,
    *(joint for finger in _FINGER_JOINTS.values() for joint in finger),
)

#: Extension-ratio thresholds — see :func:`_extension_ratio`. A finger with a
#: ratio >= ``_EXTENDED`` counts as extended; <= ``_FOLDED`` as folded; between
#: the two as bent (curled). Tunable knobs, tuned against the synthetic tests.
_EXTENDED = 0.85
_FOLDED = 0.60

#: Normalized distances (in palm lengths) for the thumb-placement tests.
_THUMB_NEAR_INDEX_MCP = 0.60  # thumb folded across the index knuckle
_THUMB_NEAR_FINGERTIPS = 0.50  # thumb tip touching the folded-fingertip cluster
_THUMB_NEAR_INDEX_TIP = 0.40  # F: thumb + index pinch
_SPREAD_V = 25.0  # degrees between index and middle directions -> V (else U/R)
_THUMB_PERPENDICULAR = 60.0  # degrees between thumb and index -> L (else G)
_TIPS_TOGETHER = 0.50  # normalized index<->middle tip gap below which crossing counts
_FIST_CLUSTER = 0.45  # mean pairwise fingertip gap (in palm lengths) for a true fist
_FIST_PALM_DIST = 0.55  # mean fingertip->palm-center distance (in palm lengths)

#: A hand whose landmarks are all this close to the origin is treated as absent
#: (MediaPipe emits an all-zero hand when no hand is detected in the frame).
_ABSENT_EPS = 1e-4


@dataclass(frozen=True)
class Handshape:
    """A classified manual-alphabet letter with a heuristic confidence in [0, 1]."""

    letter: str
    confidence: float


@dataclass(frozen=True)
class _HandFeatures:
    """Geometry features of one hand, in normalized units where sensible."""

    extended: frozenset[str]
    folded: frozenset[str]
    thumb_curl: float  # extension ratio of the thumb
    thumb_index_angle: float  # degrees between thumb and index directions
    index_middle_spread: float  # degrees between index and middle directions
    thumb_across: bool  # thumb tip near the index knuckle (folded across palm)
    thumb_opposed: bool  # thumb tip near the folded-fingertip cluster
    thumb_pinches_index: bool  # thumb tip near the index TIP (F handshape)
    crossed: bool  # index/middle tips' depth order swapped vs their MCPs (R)
    fingertips_clustered: bool  # folded fingertips gathered tightly together (fist)
    tips_near_palm: bool  # folded fingertips tucked in toward the palm center (fist)


def classify_handshape(pose: Pose, frame: int = 0) -> Handshape | None:
    """Classify the dominant hand of one skeleton frame as an ASL letter.

    Picks the hand with the greater landmark spread (right hand wins ties —
    no handedness prior is assumed otherwise). Returns ``None`` when no usable
    hand is present or no rule matches.
    """
    hand = _dominant_hand(pose, frame)
    if hand is None:
        return None
    feats = _features(hand)
    return _classify(feats)


# ---------------------------------------------------------------------------
# landmark access
# ---------------------------------------------------------------------------


def _vec(
    a: tuple[float, float, float], b: tuple[float, float, float]
) -> tuple[float, float, float]:
    return (b[0] - a[0], b[1] - a[1], b[2] - a[2])


def _norm(v: tuple[float, float, float]) -> float:
    return math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])


def _angle_between(u: tuple[float, float, float], v: tuple[float, float, float]) -> float:
    denom = _norm(u) * _norm(v)
    if denom == 0.0:
        return 90.0
    cos = (u[0] * v[0] + u[1] * v[1] + u[2] * v[2]) / denom
    return math.degrees(math.acos(max(-1.0, min(1.0, cos))))


def _extension_ratio(
    pts: dict[str, tuple[float, float, float]], joints: tuple[str, str, str, str]
) -> float:
    """Straight-line first-joint->tip distance over the sum of segment lengths.

    ~1.0 = fully extended, ~0.3-0.5 = folded into the palm, between = curled.
    Robust to translation/scale because it is a ratio.
    """
    a, b, c, d = (_point(pts, j) for j in joints)
    path = _norm(_vec(a, b)) + _norm(_vec(b, c)) + _norm(_vec(c, d))
    if path == 0.0:
        return 0.0
    return _norm(_vec(a, d)) / path


def _point(
    pts: dict[str, tuple[float, float, float]], name: str
) -> tuple[float, float, float]:
    return pts[name]


def _dominant_hand(pose: Pose, frame: int) -> dict[str, tuple[float, float, float]] | None:
    """Return landmarks for the hand with more landmark spread, or None."""
    keypoints = pose_to_keypoints(pose, frame)
    best: dict[str, tuple[float, float, float]] | None = None
    best_spread = -1.0
    for side in ("left", "right"):
        pts: dict[str, tuple[float, float, float]] = {}
        spread = 0.0
        for name in _HAND_NAMES:
            kp = keypoints[_INDEX[f"{side}_hand_{name}"]]
            pt = (float(kp.x), float(kp.y), float(kp.z))
            pts[name] = pt
            spread += abs(pt[0]) + abs(pt[1]) + abs(pt[2])
        if spread > best_spread:
            best, best_spread = pts, spread
    if best is None or best_spread <= _ABSENT_EPS * len(_HAND_NAMES):
        return None
    return best


def _features(pts: dict[str, tuple[float, float, float]]) -> _HandFeatures:
    wrist = _point(pts, "wrist")
    middle_mcp = _point(pts, "middle_mcp")
    palm = _norm(_vec(wrist, middle_mcp)) or 1.0

    extended: set[str] = set()
    folded: set[str] = set()
    for finger, joints in _FINGER_JOINTS.items():
        ratio = _extension_ratio(pts, joints)
        if ratio >= _EXTENDED:
            extended.add(finger)
        elif ratio <= _FOLDED:
            folded.add(finger)

    thumb_curl = _extension_ratio(pts, _THUMB_JOINTS)
    thumb_tip = _point(pts, "thumb_tip")
    index_tip = _point(pts, "index_tip")
    thumb_dir = _vec(_point(pts, "thumb_cmc"), thumb_tip)
    index_dir = _vec(_point(pts, "index_mcp"), index_tip)

    fingertips = [_point(pts, f"{f}_tip") for f in ("index", "middle", "ring", "pinky")]
    avg_tip = (
        sum(c[0] for c in fingertips) / 4.0,
        sum(c[1] for c in fingertips) / 4.0,
        sum(c[2] for c in fingertips) / 4.0,
    )
    pairwise = [
        _norm(_vec(fingertips[i], fingertips[j]))
        for i in range(4)
        for j in range(i + 1, 4)
    ]

    return _HandFeatures(
        extended=frozenset(extended),
        folded=frozenset(folded),
        thumb_curl=thumb_curl,
        thumb_index_angle=_angle_between(thumb_dir, index_dir),
        index_middle_spread=_angle_between(
            index_dir, _vec(_point(pts, "middle_mcp"), _point(pts, "middle_tip"))
        ),
        thumb_across=_norm(_vec(thumb_tip, _point(pts, "index_mcp"))) / palm
        < _THUMB_NEAR_INDEX_MCP,
        thumb_opposed=_norm(_vec(thumb_tip, avg_tip)) / palm < _THUMB_NEAR_FINGERTIPS,
        thumb_pinches_index=_norm(_vec(thumb_tip, index_tip)) / palm < _THUMB_NEAR_INDEX_TIP,
        crossed=(
            (_point(pts, "index_mcp")[2] - _point(pts, "middle_mcp")[2])
            * (index_tip[2] - _point(pts, "middle_tip")[2])
            < 0
        )
        and _norm(_vec(index_tip, _point(pts, "middle_tip"))) / palm < _TIPS_TOGETHER,
        fingertips_clustered=sum(pairwise) / len(pairwise) / palm < _FIST_CLUSTER,
        tips_near_palm=_norm(_vec(avg_tip, middle_mcp)) / palm < _FIST_PALM_DIST,
    )


# ---------------------------------------------------------------------------
# rules
# ---------------------------------------------------------------------------


def _classify(f: _HandFeatures) -> Handshape | None:
    """Match handshape features against the static ASL manual alphabet."""
    ext, folded = f.extended, f.folded
    n_ext = len(ext)
    thumb_out = (
        f.thumb_curl >= _EXTENDED and not f.thumb_across and not f.thumb_opposed
    )

    # --- all four fingers folded into a tight fist: A (S/T share it) ---
    # The fingertip cluster + palm-distance guards separate a real fist from any
    # random low-ratio arrangement of landmarks (noise poses don't cluster tips).
    if (
        n_ext == 0
        and len(folded) == 4
        and f.fingertips_clustered
        and f.tips_near_palm
    ):
        return Handshape("a", 0.9)

    # --- all four extended: B ---
    if n_ext == 4:
        return Handshape("b", 0.9 if f.thumb_across else 0.6)

    # --- all four bent (none extended, none folded): C ---
    if n_ext == 0 and len(folded) == 0:
        return Handshape("c", 0.6)

    # --- F: index curls to pinch the thumb; the other three stay extended ---
    if ext == {"middle", "ring", "pinky"} and "index" not in ext and f.thumb_pinches_index:
        return Handshape("f", 0.9)

    # --- exactly one extended ---
    if n_ext == 1:
        if "index" in ext:
            if thumb_out and f.thumb_pinches_index and f.thumb_index_angle < _THUMB_PERPENDICULAR:
                return Handshape("g", 0.9)  # G: thumb pad along the extended index
            if thumb_out:
                return Handshape("l", 0.9)  # L: thumb out perpendicular
            return Handshape("d", 0.9)  # D: index up, thumb folded across
        if "pinky" in ext:
            return Handshape("y", 0.9) if thumb_out else Handshape("i", 0.9)
        return None

    # --- exactly two extended ---
    if n_ext == 2:
        if ext == {"index", "middle"}:
            if f.index_middle_spread >= _SPREAD_V:
                return Handshape("v", 0.9)  # V: spread index + middle
            if f.crossed:
                return Handshape("r", 0.6)  # R: crossed (depth-order swap)
            return Handshape("u", 0.9)  # U (H shares this shape — see module note)
        return None

    # --- exactly three extended: W ---
    if n_ext == 3:
        if ext == {"index", "middle", "ring"}:
            return Handshape("w", 0.9)  # W: three up, pinky folded
        return None

    return None
