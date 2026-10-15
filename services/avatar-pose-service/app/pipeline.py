"""avatar-pose pipeline: transcript + translation -> ``ai.avatar.pose.frame``.

Consumes both text inputs the avatar renders from (ai-services-IMPLEMENTATION.md §"Service
map"), closing the loop in both directions:

* ``ai.transcript.segment``  — speech in, avatar signs it (hearing speaker -> Deaf audience).
* ``ai.translation.result`` — the **Deaf-presenter leg** and the only reason this
  service exists as a *bidirectional* tool: a Deaf presenter signs, sign-recognition
  recognizes the gloss, translation renders it, and the avatar signs the translated
  text back out so hearing participants can *see* what was said. Without this input the
  service is captions-only in reverse.
"""

from __future__ import annotations

from typing import NamedTuple

from inclusaai_ai_core import BaseInferencePipeline
from inclusaai_contracts.events import AccessibilityChannel, TranscriptSegment, TranslationResult
from inclusaai_utils import now_ms
from pydantic import BaseModel

from app.config import Settings
from app.inference.engine import PoseEngine
from app.postprocessing import to_frames


class _TextRequest(NamedTuple):
    """The one thing both input events agree on: what to sign, and when from."""

    session_id: str
    text: str
    start_ms: int


def _as_request(model: BaseModel) -> _TextRequest | None:
    """Project either input event onto ``(session_id, text, start_ms)``; None if neither.

    The avatar signs the **target** language on the translation leg — that is the whole
    point of the render, so it is ``translated_text``, never ``source_text``.

    ``TranslationResult`` carries no segment timing, so that leg anchors on arrival
    (``now_ms()``) rather than the source segment's own start. The clean fix is segment
    timing on the contract; deliberately not guessed at here.
    """
    if isinstance(model, TranscriptSegment):
        return _TextRequest(model.session_id, model.text, model.start_ms)
    if isinstance(model, TranslationResult):
        return _TextRequest(model.session_id, model.translated_text, now_ms())
    return None


class AvatarPosePipeline(BaseInferencePipeline):
    output_channel = AccessibilityChannel.AVATAR
    usage_unit = "avatar_pose_frame"

    def __init__(self, settings: Settings) -> None:
        super().__init__(
            settings, topics=["ai.transcript.segment", "ai.translation.result"]
        )
        self.fps = settings.fps
        self.engine = PoseEngine(settings)

    async def on_start(self) -> None:
        self.engine.load()

    async def handle(self, event_key: str, model: BaseModel) -> None:
        request = _as_request(model)
        if request is None:
            return
        if not self.should_generate(request.session_id):
            return
        phrase_id, pose = self.engine.generate(request.text)
        for frame in to_frames(
            request.session_id, request.start_ms, phrase_id, pose, self.fps
        ):
            # one usage unit per emitted pose frame
            await self.publish("ai.avatar.pose.frame", frame, key=request.session_id)
