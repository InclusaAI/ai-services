"""vision-quality pipeline: ``media.*.video.frame`` -> ``ai.vision.quality.signal``."""

from __future__ import annotations

from inclusaai_ai_core import BaseInferencePipeline
from inclusaai_contracts.events import VideoFrame
from inclusaai_kafka_clients.topics import VIDEO_FRAME_SUBSCRIPTION
from pydantic import BaseModel

from app.config import Settings
from app.inference.engine import VisionQualityEngine
from app.postprocessing import to_signal
from app.preprocessing import decode_frame


class VisionQualityPipeline(BaseInferencePipeline):
    # Presenter-assist feedback, not a per-participant accessibility channel -> always on.
    # TODO(throttle): emit on change / at a low cadence rather than one signal per frame.
    output_channel = None
    usage_unit = "quality_signal"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings, subscription=VIDEO_FRAME_SUBSCRIPTION)
        self.engine = VisionQualityEngine(settings)

    async def on_start(self) -> None:
        self.engine.load()

    async def handle(self, event_key: str, model: BaseModel) -> None:
        if not isinstance(model, VideoFrame):
            return
        assessment = self.engine.assess(decode_frame(model))
        signal = to_signal(model, assessment)
        await self.publish("ai.vision.quality.signal", signal, key=model.session_id)
