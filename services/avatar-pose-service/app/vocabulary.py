"""Constrained-vocabulary signing library (ADR-0002).

The avatar generates from a fixed, curated set of phrases (~150-300 in the real
library) — the SAME closed set the sign-recognition service classifies against
(symmetric vocabulary). Out-of-vocabulary content falls back to a neutral pose in
the scaffold; production would fingerspell it.
"""

from __future__ import annotations

from inclusaai_contracts.events import PoseKeypoint

PoseFrames = list[list[PoseKeypoint]]

# TODO(vocab): replace with the real curated library (shared with sign-recognition).
_LIBRARY: dict[str, PoseFrames] = {
    "hello": [[PoseKeypoint(x=0.0, y=0.0)], [PoseKeypoint(x=0.1, y=0.1)]],
    "thank you": [[PoseKeypoint(x=0.2, y=0.0)], [PoseKeypoint(x=0.2, y=0.2)]],
}

_NEUTRAL: PoseFrames = [[PoseKeypoint(x=0.0, y=0.0)]]


def lookup(text: str) -> tuple[str | None, PoseFrames]:
    """Map free text to a (phrase_id, pose-frame-sequence). Neutral when OOV."""
    key = text.strip().lower()
    for phrase, frames in _LIBRARY.items():
        if phrase in key:
            return phrase, frames
    return None, _NEUTRAL
