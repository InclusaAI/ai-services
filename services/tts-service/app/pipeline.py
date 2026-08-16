"""tts pipeline: ``ai.translation.result`` -> ``ai.tts.audio.chunk``."""

from __future__ import annotations

from collections import defaultdict

from pydantic import BaseModel

from inclusaai_ai_core import BaseInferencePipeline
from inclusaai_contracts.events import AccessibilityChannel, TranslationResult

from app.config import Settings
from app.inference.engine import TtsEngine
from app.postprocessing import to_chunk


class TtsPipeline(BaseInferencePipeline):
    output_channel = AccessibilityChannel.TTS
    usage_unit = "tts_chunk"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings, topics=["ai.translation.result"])
        self.sample_rate = settings.sample_rate
        self.encoding = settings.encoding
        self.engine = TtsEngine(settings)
        self._seq: dict[str, int] = defaultdict(int)

    async def on_start(self) -> None:
        self.engine.load()

    async def handle(self, event_key: str, model: BaseModel) -> None:
        if not isinstance(model, TranslationResult):
            return
        if not self.should_generate(model.session_id):
            return
        audio = self.engine.synthesize(model.translated_text, language=model.target_language)
        seq = self._seq[model.session_id]
        self._seq[model.session_id] += 1
        chunk = to_chunk(
            model, audio, sequence=seq, sample_rate=self.sample_rate, encoding=self.encoding
        )
        await self.publish("ai.tts.audio.chunk", chunk, key=model.session_id)
