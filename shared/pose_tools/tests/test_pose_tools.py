"""Tests for inclusaai_pose_tools — conversion round-trips, holistic subsetting,
serialization, and the deterministic code helpers. All mediapipe-free."""

from __future__ import annotations

import inclusaai_pose_tools as pt
import numpy as np
import numpy.ma as ma
from inclusaai_contracts.events import PoseKeypoint
from inclusaai_sign_vocab.skeleton import NUM_KEYPOINTS, SKELETON
from pose_format import Pose
from pose_format.numpy.pose_body import NumPyPoseBody
from pose_format.pose_header import (
    PoseHeader,
    PoseHeaderComponent,
    PoseHeaderDimensions,
)

# ---------------------------------------------------------------------------
# header
# ---------------------------------------------------------------------------


def test_skeleton_header_matches_sign_vocab():
    header = pt.skeleton_header()
    assert header.total_points() == NUM_KEYPOINTS == 51
    assert header.num_dims() == 3  # XYZC → 3 spatial dims
    names = [c.name for c in header.components]
    assert names == ["body", "left_hand", "right_hand"]
    counts = [len(c.points) for c in header.components]
    assert counts == [9, 21, 21]
    # Concatenated component points reproduce SKELETON in order.
    flat = [p for c in header.components for p in c.points]
    assert flat == list(SKELETON)


def test_skeleton_header_is_cached():
    assert pt.skeleton_header() is pt.skeleton_header()


# ---------------------------------------------------------------------------
# convert round-trip
# ---------------------------------------------------------------------------


def _make_frames(num_frames: int) -> list[list[PoseKeypoint]]:
    frames = []
    for f in range(num_frames):
        kps = [
            PoseKeypoint(
                x=float(f * 100 + i),
                y=float(f * 100 + i) + 0.5,
                z=float(f * 100 + i) + 0.25,
                visibility=(i % 10) / 10.0,
            )
            for i in range(NUM_KEYPOINTS)
        ]
        frames.append(kps)
    return frames


def test_keypoints_pose_roundtrip():
    frames = _make_frames(3)
    pose = pt.keypoints_to_pose(frames, fps=30)
    assert pt.frame_count(pose) == 3
    for f in range(3):
        out = pt.pose_to_keypoints(pose, f)
        assert len(out) == NUM_KEYPOINTS
        for i, kp in enumerate(out):
            assert kp.x == frames[f][i].x
            assert kp.y == frames[f][i].y
            assert kp.z == frames[f][i].z
            assert abs(kp.visibility - frames[f][i].visibility) < 1e-6


def test_keypoints_to_pose_empty_frames_gives_one_frame():
    pose = pt.keypoints_to_pose([], fps=30)
    assert pt.frame_count(pose) == 1


# ---------------------------------------------------------------------------
# codes
# ---------------------------------------------------------------------------


def test_pose_for_code_roundtrips_through_pose_code():
    for code in (0, 1, 7, 42, 199, 255):
        assert pt.pose_code(pt.pose_for_code(code)) == code


# ---------------------------------------------------------------------------
# fakes
# ---------------------------------------------------------------------------


def test_fake_skeleton_pose_is_deterministic():
    a = pt.fake_skeleton_pose(8, seed=123)
    b = pt.fake_skeleton_pose(8, seed=123)
    assert pt.frame_count(a) == 8
    assert np.array_equal(np.asarray(a.body.data), np.asarray(b.body.data))
    c = pt.fake_skeleton_pose(8, seed=999)
    assert not np.array_equal(np.asarray(a.body.data), np.asarray(c.body.data))


# ---------------------------------------------------------------------------
# serialize
# ---------------------------------------------------------------------------


def test_pose_bytes_roundtrip():
    frames = _make_frames(2)
    pose = pt.keypoints_to_pose(frames, fps=30)
    data = pt.to_pose_bytes(pose)
    assert isinstance(data, bytes) and len(data) > 0
    restored = pt.read_pose_bytes(data)
    assert pt.frame_count(restored) == 2
    assert restored.header.total_points() == NUM_KEYPOINTS
    out = pt.pose_to_keypoints(restored, 0)
    for i, kp in enumerate(out):
        assert abs(kp.x - frames[0][i].x) < 1e-3


# ---------------------------------------------------------------------------
# holistic → skeleton  (synthetic holistic pose, mediapipe-free)
# ---------------------------------------------------------------------------

# The 33 MediaPipe PoseLandmark names, in enum order (0..32).
_MP_POSE_NAMES = [
    "NOSE",
    "LEFT_EYE_INNER", "LEFT_EYE", "LEFT_EYE_OUTER",
    "RIGHT_EYE_INNER", "RIGHT_EYE", "RIGHT_EYE_OUTER",
    "LEFT_EAR", "RIGHT_EAR",
    "MOUTH_LEFT", "MOUTH_RIGHT",
    "LEFT_SHOULDER", "RIGHT_SHOULDER",
    "LEFT_ELBOW", "RIGHT_ELBOW",
    "LEFT_WRIST", "RIGHT_WRIST",
    "LEFT_PINKY", "RIGHT_PINKY",
    "LEFT_INDEX", "RIGHT_INDEX",
    "LEFT_THUMB", "RIGHT_THUMB",
    "LEFT_HIP", "RIGHT_HIP",
    "LEFT_KNEE", "RIGHT_KNEE",
    "LEFT_ANKLE", "RIGHT_ANKLE",
    "LEFT_HEEL", "RIGHT_HEEL",
    "LEFT_FOOT_INDEX", "RIGHT_FOOT_INDEX",
]
_MP_HAND_NAMES = [f"HAND_{i}" for i in range(21)]  # names irrelevant, count matters


def _component(name: str, point_names: list[str]) -> PoseHeaderComponent:
    return PoseHeaderComponent(
        name=name,
        points=point_names,
        limbs=[],
        colors=[(255, 255, 255)],
        point_format="XYZC",
    )


def _fake_holistic_pose(num_frames: int = 2) -> Pose:
    """Build a Holistic-shaped pose (543 pts) whose every point's X == its global
    flat index, so we can verify holistic_to_skeleton picks the right points."""
    components = [
        _component("POSE_LANDMARKS", _MP_POSE_NAMES),          # 33
        _component("FACE_LANDMARKS", [f"F_{i}" for i in range(468)]),  # 468
        _component("LEFT_HAND_LANDMARKS", _MP_HAND_NAMES),     # 21
        _component("RIGHT_HAND_LANDMARKS", _MP_HAND_NAMES),    # 21
        _component("POSE_WORLD_LANDMARKS", _MP_POSE_NAMES),    # 33
    ]
    header = PoseHeader(
        version=0.2,
        dimensions=PoseHeaderDimensions(width=1, height=1, depth=1),
        components=components,
    )
    total = header.total_points()
    assert total == 33 + 468 + 21 + 21 + 33 == 576
    data = np.zeros((num_frames, 1, total, 3), dtype=np.float32)
    for i in range(total):
        data[:, :, i, 0] = float(i)  # encode global index into X
    confidence = np.ones((num_frames, 1, total), dtype=np.float32)
    body = NumPyPoseBody(fps=25.0, data=ma.masked_array(data), confidence=confidence)
    return Pose(header, body)


def test_holistic_to_skeleton_selects_51_points_in_order():
    holistic = _fake_holistic_pose(num_frames=2)
    skel = pt.holistic_to_skeleton(holistic)

    # shape / header
    assert skel.header.total_points() == NUM_KEYPOINTS == 51
    assert [c.name for c in skel.header.components] == ["body", "left_hand", "right_hand"]
    assert pt.frame_count(skel) == 2

    # Each point's X still equals its ORIGINAL holistic global index, proving the
    # right points were selected in the right order.
    xs = np.asarray(skel.body.data)[0, 0, :, 0].tolist()
    body_expected = [0, 11, 12, 13, 14, 15, 16, 23, 24]        # NOSE, shoulders...hips
    left_expected = list(range(33 + 468, 33 + 468 + 21))       # 501..521
    right_expected = list(range(33 + 468 + 21, 33 + 468 + 42))  # 522..542
    assert xs == [float(v) for v in body_expected + left_expected + right_expected]
