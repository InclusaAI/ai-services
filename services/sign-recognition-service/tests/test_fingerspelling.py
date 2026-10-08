"""Tests for the rule-based fingerspelling classifier.

These are **mediapipe-free**: they build synthetic 51-point poses whose right
hand is posed as a specific letter (``tests/handshapes.py``) and assert the
classifier resolves them. They pin the feature-extraction and rule logic, not
real-world generalization — the real path stays gated behind
``SIGN_RUN_MEDIAPIPE_TESTS=1`` and, ultimately, a learned model (ADR-0002).
"""

from __future__ import annotations

import pytest
from app.inference.fingerspelling import classify_handshape

from tests.handshapes import LETTERS, handshape_pose


@pytest.mark.parametrize("letter", sorted(LETTERS))
def test_classifier_recognizes_each_static_letter(letter: str) -> None:
    shape = classify_handshape(handshape_pose(letter))
    assert shape is not None, f"expected a handshape for {letter!r}"
    assert shape.letter == letter
    assert 0.0 < shape.confidence <= 1.0


def test_pose_without_a_hand_is_not_a_letter() -> None:
    """pose_for_code builds a pose with zeroed hands -> nothing to classify."""
    from inclusaai_pose_tools import pose_for_code

    assert classify_handshape(pose_for_code(1)) is None
    assert classify_handshape(pose_for_code(0)) is None


def test_noise_poses_rarely_false_positive() -> None:
    """Random skeletons must not masquerade as letters at any meaningful rate."""
    from inclusaai_pose_tools import fake_skeleton_pose

    hits = sum(
        1
        for seed in range(500)
        if classify_handshape(fake_skeleton_pose(1, seed=seed)) is not None
    )
    # The static rules are narrow (measured ~2%); a <4% false-positive bound is
    # far above the expected ~11 hits but still catches a rule regression that
    # fires broadly.
    assert hits <= 20, f"noise classified as a letter {hits} times out of 500"
