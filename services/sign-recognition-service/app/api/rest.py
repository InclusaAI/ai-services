"""Service-specific REST routes (health/metrics come from ai_core).

A synchronous, single-frame view of the engine for smoke-testing and debugging without
a broker or GPU. The Kafka pipeline (:mod:`app.pipeline`) is the production path and
differs in one meaningful way: it buffers a **gesture window** and majority-votes
before publishing. This endpoint classifies the one frame it is given, so a noisy frame
here can flip a label that the pipeline would have smoothed out.
"""

from __future__ import annotations

from fastapi import APIRouter
from inclusaai_contracts.events import SignRecognitionResult, VideoFrame
from inclusaai_sign_vocab import FINGERSPELL_ALPHABET, phrase_ids

from app.config import Settings
from app.detection import extract_landmarks
from app.inference.engine import SignEngine
from app.postprocessing import to_result
from app.preprocessing import decode_frame


def build_router(engine: SignEngine, settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/v1", tags=["sign-recognition"])

    @router.post("/recognize", response_model=list[SignRecognitionResult])
    def recognize(frame: VideoFrame) -> list[SignRecognitionResult]:
        """Recognize one video frame (JSON body, base64 ``payload_b64`` e.g. JPEG).

        Returns one result when the frame classifies, and an empty list when there is
        nothing to recognize (empty payload -> no pose -> no phantom emission).
        MediaPipe is used when installed; otherwise the offline placeholder pose is
        used and the response is the deterministic closed-set stub.
        """
        pose = extract_landmarks(decode_frame(frame))
        if pose is None:
            return []
        return [
            to_result(frame, recognition, settings.sign_language)
            for recognition in engine.recognize(pose)
        ]

    @router.get("/labels")
    def labels() -> dict[str, object]:
        """The closed label set this service can emit (ADR-0002 symmetric vocabulary).

        Every ``phrase`` id here is one the avatar-pose service can render, and every
        ``fingerspelling`` letter is one it can spell out — the matched-pair guarantee.
        """
        return {
            "sign_language": settings.sign_language,
            "phrases": phrase_ids(),
            "fingerspelling": list(FINGERSPELL_ALPHABET),
            "gesture_window_frames": settings.gesture_window_frames,
            "video_sample_fps": settings.video_sample_fps,
        }

    return router
