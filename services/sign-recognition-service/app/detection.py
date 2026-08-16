"""Landmark detection (MediaPipe Hands/Holistic in production).

Extracts hand/pose keypoints from a frame; the recognition model classifies
sequences of these rather than raw pixels.
"""

from __future__ import annotations

Landmarks = list[float]


def extract_landmarks(image_bytes: bytes) -> Landmarks:
    """Extract hand/pose landmarks from a decoded frame.

    TODO(mediapipe): run MediaPipe Holistic and flatten the hand/pose keypoints.
    The placeholder returns an empty vector for an empty frame and a short
    deterministic vector otherwise, so the pipeline is exercisable offline.
    """
    if not image_bytes:
        return []
    return [float(len(image_bytes) % 256)]
