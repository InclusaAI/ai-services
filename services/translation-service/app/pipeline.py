"""translation pipeline: ``ai.transcript.segment`` -> ``ai.translation.result``."""

from __future__ import annotations

from inclusaai_ai_core import BaseInferencePipeline
from inclusaai_contracts.events import AccessibilityChannel, TranscriptSegment
from pydantic import BaseModel

from app import language
from app.config import Settings
from app.inference.engine import TranslationEngine
from app.postprocessing import to_result


class TranslationPipeline(BaseInferencePipeline):
    output_channel = AccessibilityChannel.TRANSLATION
    usage_unit = "translation"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings, topics=["ai.transcript.segment"])
        self.source = language.normalize(settings.default_source_language)
        self.target = language.normalize(settings.default_target_language)
        self.engine = TranslationEngine(settings)

    async def on_start(self) -> None:
        self.engine.load()

    async def handle(self, event_key: str, model: BaseModel) -> None:
        if not isinstance(model, TranscriptSegment):
            return
        # Preference gate: skip when no participant in the session wants translation.
        if not self.should_generate(model.session_id):
            return
        source = language.normalize(model.language) or self.source
        translated = self.engine.translate(model.text, source=source, target=self.target)
        result = to_result(model, translated, source=source, target=self.target)
        await self.publish("ai.translation.result", result, key=model.session_id)
