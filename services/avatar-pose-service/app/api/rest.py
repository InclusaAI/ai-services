"""Service-specific REST routes (health/metrics come from ai_core).

A synchronous, single-request view of the generator for smoke-testing and debugging
without a broker or GPU. The Kafka pipeline (:mod:`app.pipeline`) is the production
path; the pose sequence produced here is identical, just driven by one REST body.

Every request body carries a filled-in OpenAPI ``example``, so ``/docs`` "Try it out"
sends a request that actually works instead of an empty schema-shaped stub.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body
from inclusaai_contracts.events import AvatarPoseFrame
from inclusaai_sign_vocab import FINGERSPELL_ALPHABET, PHRASES, phrase_ids
from inclusaai_utils import now_ms
from pydantic import BaseModel, Field

from app.config import Settings
from app.inference.engine import PoseEngine
from app.postprocessing import to_frames


class PoseRequest(BaseModel):
    """Text to sign. Mirrors what the pipeline receives on either input topic."""

    text: str = Field(
        description="transcript or translated text to render as a pose",
        json_schema_extra={"examples": ["hello there"]},
    )
    session_id: str = Field(
        default="rest", description="echoed onto every emitted frame"
    )
    start_ms: int | None = Field(
        default=None,
        description="timeline anchor; defaults to now (no source timing on the REST path)",
    )


_POSE_EXAMPLE: dict[str, object] = {
    "text": "hello there",
    "session_id": "demo-session",
    "start_ms": 0,
}

_POSE_RESPONSES: dict[int | str, dict[str, object]] = {
    200: {
        "description": (
            "One frame per animation frame of the generated pose. `phrase_id` is the "
            "matched closed-set phrase, or null when the text was out-of-vocabulary "
            "(fingerspelled) or empty (neutral resting frame)."
        )
    }
}


def build_router(engine: PoseEngine, settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/v1", tags=["avatar-pose"])

    @router.post(
        "/pose",
        response_model=list[AvatarPoseFrame],
        responses=_POSE_RESPONSES,
        summary="Generate the pose frame sequence for some text",
    )
    def pose(
        request: Annotated[
            PoseRequest,
            # A dict, not a list: OpenAPI requires `examples` to be a MAP. A list is
            # passed through as an invalid array and Swagger UI falls back to the
            # schema, so no example renders.
            Body(openapi_examples={"signText": _POSE_EXAMPLE}),
        ],
    ) -> list[AvatarPoseFrame]:
        """In-vocabulary text returns the phrase's frames with its ``phrase_id`` set;
        out-of-vocabulary text is fingerspelled (``phrase_id`` null); empty text
        returns a single neutral resting frame.
        """
        phrase_id, generated = engine.generate(request.text)
        start_ms = now_ms() if request.start_ms is None else request.start_ms
        return to_frames(
            request.session_id, start_ms, phrase_id, generated, settings.fps
        )

    @router.get("/vocabulary", summary="The closed set this service can render")
    def vocabulary() -> dict[str, object]:
        """Identical to what the sign-recognition service classifies against, so the
        two cannot drift — the matched-pair guarantee (ADR-0002).
        """
        return {
            "fps": settings.fps,
            "phrases": [
                {"id": entry.id, "gloss": entry.gloss, "category": entry.category}
                for entry in PHRASES
            ],
            "phrase_count": len(phrase_ids()),
            "fingerspelling": list(FINGERSPELL_ALPHABET),
        }

    return router
