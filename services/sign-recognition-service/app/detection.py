"""Landmark detection: a video frame -> InclusaAI 51-point skeleton ``Pose``.

Runs **MediaPipe Holistic** (via pose-format's ``load_holistic``) to extract the
pose core plus both hands, then subsets to the shared 51-point ``SKELETON`` (the
face is dropped) with :func:`inclusaai_pose_tools.holistic_to_skeleton`.

``cv2`` and ``mediapipe`` are optional heavy dependencies, imported lazily. When
they (or their native libraries) are unavailable, or a frame cannot be processed,
extraction degrades to a deterministic fake pose with a loud
``sign.mediapipe_unavailable`` log — so the service stays bootable and the pipeline
stays exercisable offline, mirroring asr's ``WhisperBackend`` degrade path. Real
recognition *content* remains gated on ADR-0002; this is perception plumbing only.
"""

from __future__ import annotations

import numpy as np
from inclusaai_pose_tools import fake_skeleton_pose, holistic_to_skeleton
from inclusaai_telemetry import get_logger
from pose_format import Pose

log = get_logger(__name__)

# fps is metadata only for single-frame extraction; use the ADR-0007 sampling rate.
_FPS = 15


class _HolisticBackend:
    """MediaPipe Holistic extraction, wrapped to emit a 51-point skeleton ``Pose``.

    ``cv2`` and pose-format's ``load_holistic`` (which imports ``mediapipe``) are
    imported lazily here, so importing this module never requires them.
    """

    def __init__(self) -> None:
        import cv2  # lazy: optional heavy dep (opencv)
        from pose_format.utils.holistic import load_holistic  # lazy: imports mediapipe

        self._cv2 = cv2
        self._load_holistic = load_holistic
        log.info("sign.mediapipe.loaded")

    def extract(self, image_bytes: bytes) -> Pose:
        cv2 = self._cv2
        buffer = np.frombuffer(image_bytes, dtype=np.uint8)
        bgr = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
        if bgr is None:
            raise ValueError("opencv could not decode the frame bytes as an image")
        # MediaPipe expects RGB; opencv decodes to BGR.
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        height, width = rgb.shape[:2]
        holistic = self._load_holistic(
            [rgb],
            fps=_FPS,
            width=width,
            height=height,
            # each frame independent (no cross-frame tracking yet); no face mesh needed.
            additional_holistic_config={
                "static_image_mode": True,
                "refine_face_landmarks": False,
            },
        )
        return holistic_to_skeleton(holistic)


_backend: _HolisticBackend | None = None
_backend_unavailable = False


def _get_backend() -> _HolisticBackend | None:
    """Return the holistic backend, or ``None`` if its deps can't be imported.

    Import is attempted once; the outcome (backend or unavailable) is cached so we
    neither re-pay the heavy import nor re-log its absence per frame.
    """
    global _backend, _backend_unavailable
    if _backend is not None:
        return _backend
    if _backend_unavailable:
        return None
    try:
        _backend = _HolisticBackend()
    except Exception as exc:  # noqa: BLE001 — degrade to a fake pose, but say why (loudly)
        log.error("sign.mediapipe_unavailable", error=str(exc))
        _backend_unavailable = True
        return None
    return _backend


def extract_landmarks(image_bytes: bytes) -> Pose | None:
    """Extract a 51-point skeleton ``Pose`` from one encoded video frame.

    * empty bytes -> ``None`` (nothing to detect; the engine emits nothing).
    * MediaPipe/opencv available -> real Holistic landmarks, subset to the skeleton.
    * unavailable / undecodable frame -> deterministic fake pose seeded by frame size
      (offline-boot), so the pipeline is still exercisable.
    """
    if not image_bytes:
        return None
    backend = _get_backend()
    if backend is not None:
        try:
            return backend.extract(image_bytes)
        except Exception as exc:  # noqa: BLE001 — one bad frame shouldn't kill the stream
            log.warning("sign.extract_failed", error=str(exc))
    return fake_skeleton_pose(1, seed=len(image_bytes))
