"""avatar-pose pipeline: ``ai.transcript.segment`` -> ``ai.avatar.pose.frame``."""

from __future__ import annotations

from inclusaai_ai_core import BaseInferencePipeline
from inclusaai_contracts.events import AccessibilityChannel, TranscriptSegment
from pydantic import BaseModel

from app.config import Settings
from app.inference.engine import PoseEngine
from app.postprocessing import to_frames


class AvatarPosePipeline(BaseInferencePipeline):
    output_channel = AccessibilityChannel.AVATAR
    usage_unit = "avatar_pose_frame"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings, topics=["ai.transcript.segment"])
        self.fps = settings.fps
        self.engine = PoseEngine(settings)

    async def on_start(self) -> None:
        self.engine.load()

    async def handle(self, event_key: str, model: BaseModel) -> None:
        if not isinstance(model, TranscriptSegment):
            return
        if not self.should_generate(model.session_id):
            return
        phrase_id, pose = self.engine.generate(model.text)
        for frame in to_frames(model, phrase_id, pose, self.fps):
            # one usage unit per emitted pose frame
            await self.publish("ai.avatar.pose.frame", frame, key=model.session_id)
