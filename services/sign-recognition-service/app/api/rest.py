"""Service-specific REST routes (health/metrics come from ai_core).

A synchronous, single-frame view of the engine for smoke-testing and debugging without
a broker or GPU. The Kafka pipeline (:mod:`app.pipeline`) is the production path and
differs in one meaningful way: it buffers a **gesture window** and majority-votes
before publishing. This endpoint classifies the one frame it is given, so a noisy frame
here can flip a label that the pipeline would have smoothed out.

Every request body carries a filled-in OpenAPI ``example``, so ``/docs`` "Try it out"
sends a request that actually works instead of an empty schema-shaped stub.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, HTTPException
from fastapi.openapi.models import Example
from inclusaai_contracts.events import SignRecognitionResult, VideoFrame
from inclusaai_sign_vocab import FINGERSPELL_ALPHABET, phrase_ids

from app.config import Settings
from app.detection import extract_landmarks
from app.inference.engine import SignEngine
from app.postprocessing import to_result
from app.preprocessing import decode_frame

#: A tiny, real JPEG (1x1 solid grey) so the example request is
#: genuinely well-formed rather than a placeholder that only pretends to be image data.
#: It encodes no signer, so it exercises the plumbing, not detection quality.
_EXAMPLE_PAYLOAD_B64 = (
    "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0a"
    "HBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAABAAAAAAAA"
    "AAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AKp//2Q=="
)

_RECOGNIZE_EXAMPLE: dict[str, object] = {
    "session_id": "demo-session",
    "presenter_id": "presenter-1",
    "sequence": 0,
    "timestamp_ms": 0,
    "width": 1,
    "height": 1,
    "fps": 15,
    "payload_b64": _EXAMPLE_PAYLOAD_B64,
}

_RECOGNIZE_EXAMPLE_OPENAPI = Example(
    value=_RECOGNIZE_EXAMPLE,
    summary="One video frame (real 1x1 JPEG)",
)

_RECOGNIZE_ERROR_RESPONSES: dict[int | str, dict[str, object]] = {
    422: {"description": "Malformed base64 in `payload_b64`."},
    200: {
        "description": (
            "Zero or one result. An empty list means there was nothing to recognize "
            "(empty payload, or no pose extracted)."
        )
    },
}


def build_router(engine: SignEngine, settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/v1", tags=["sign-recognition"])

    @router.post(
        "/recognize",
        response_model=list[SignRecognitionResult],
        responses=_RECOGNIZE_ERROR_RESPONSES,
        summary="Recognize one video frame",
    )
    def recognize(
        frame: Annotated[
            VideoFrame,
            Body(
                # A dict, not a list: OpenAPI requires `examples` to be a MAP
                # ({"name": Example{...}}). FastAPI passes a list straight through, and
                # Swagger UI silently ignores the invalid array form and falls back
                # to the schema — which is why a list "shows no example".
                #
                # Each Example MUST have a `value` field (the actual example object).
                # FastAPI's Example model enforces this; raw dicts are invalid OpenAPI.
                openapi_examples={"recognizeFrame": _RECOGNIZE_EXAMPLE_OPENAPI},
                description=(
                    "One video frame. `payload_b64` is the base64-encoded image "
                    "(JPEG/PNG); the example above is a real 1x1 JPEG."
                ),
            ),
        ],
    ) -> list[SignRecognitionResult]:
        """Classify one frame against the closed ASL vocabulary (ADR-0002).

        Returns one `SignRecognitionResult` when the frame classifies, and an empty
        list when there is nothing to recognize (empty payload -> no pose -> no
        phantom emission).

        MediaPipe is used when installed; otherwise the offline placeholder pose is
        used and the label is the deterministic closed-set stub.
        """
        try:
            image_bytes = decode_frame(frame)
        except ValueError as exc:
            # Bad client input is a 4xx, never a 500.
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        pose = extract_landmarks(image_bytes)
        if pose is None:
            return []
        return [
            to_result(frame, recognition, settings.sign_language)
            for recognition in engine.recognize(pose)
        ]

    @router.get(
        "/labels",
        summary="The closed label set this service can emit",
    )
    def labels() -> dict[str, object]:
        """Every `phrase` id here is one the avatar-pose service can render, and every
        `fingerspelling` letter is one it can spell out — the matched-pair guarantee.
        """
        return {
            "sign_language": settings.sign_language,
            "phrases": list(phrase_ids()),
            "fingerspelling": list(FINGERSPELL_ALPHABET),
            "gesture_window_frames": settings.gesture_window_frames,
            "video_sample_fps": settings.video_sample_fps,
        }

    return router
