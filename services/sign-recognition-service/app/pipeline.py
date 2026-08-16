"""sign-recognition pipeline: ``media.*.video.frame`` -> ``ai.sign.recognition.result``."""

from __future__ import annotations

from pydantic import BaseModel

from inclusaai_ai_core import BaseInferencePipeline
from inclusaai_contracts.events import VideoFrame
from inclusaai_kafka_clients.topics import VIDEO_FRAME_SUBSCRIPTION

from app.config import Settings
from app.detection import extract_landmarks
from app.inference.engine import SignEngine
from app.postprocessing import to_result
from app.preprocessing import decode_frame


class SignPipeline(BaseInferencePipeline):
    # Recognizing a signer's input is foundational (feeds captions/translation for
    # hearing participants), so it is not gated on a single output channel.
    # TODO(gating): skip when no participant in the session is signing.
    output_channel = None
    usage_unit = "sign_segment"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings, subscription=VIDEO_FRAME_SUBSCRIPTION)
        self.sign_language = settings.sign_language
        self.engine = SignEngine(settings)

    async def on_start(self) -> None:
        self.engine.load()

    async def handle(self, event_key: str, model: BaseModel) -> None:
        if not isinstance(model, VideoFrame):
            return
        landmarks = extract_landmarks(decode_frame(model))
        for recognition in self.engine.recognize(landmarks):
            result = to_result(model, recognition, self.sign_language)
            await self.publish("ai.sign.recognition.result", result, key=model.session_id)
