"""translation pipeline: transcript + sign recognition -> ``ai.translation.result``.

Consumes both text inputs (ai-services-IMPLEMENTATION.md §"Service map"):

* ``ai.transcript.segment``      — speech in a spoken language.
* ``ai.sign.recognition.result`` — **the Deaf-presenter leg**: a Deaf presenter signs,
  sign-recognition recognizes the closed-set gloss, and this turns that gloss into a
  spoken-language target. Without it the recognizer's output had no consumer anywhere
  in the platform and the reverse direction could not exist.

Sign-gloss caveats, both consequences of ADR-0002 scoping rather than bugs here:

* The glosses are **English placeholder text** until the Deaf-community/linguist
  consultation lands, so the MT ``source`` is ``sign_gloss_source_language`` (default
  ``en``) rather than the sign language code — ``ASL`` is not a text language pair.
* A fingerspelled window carries a **single letter** (sign-recognition emits one letter
  per gesture window). Translating it in isolation yields a lone letter, not a word.
  Assembling letters into words is segmentation work that belongs with the recognizer's
  window aggregation, not here.
"""

from __future__ import annotations

from typing import NamedTuple

from inclusaai_ai_core import BaseInferencePipeline
from inclusaai_contracts.events import (
    AccessibilityChannel,
    SignRecognitionResult,
    TranscriptSegment,
)
from pydantic import BaseModel

from app import language
from app.config import Settings
from app.inference.engine import TranslationEngine
from app.postprocessing import to_result


class _TextRequest(NamedTuple):
    """What both input events agree on: what to translate, and from what language."""

    session_id: str
    segment_id: str
    text: str
    source_language: str


def _as_request(model: BaseModel, settings: Settings) -> _TextRequest | None:
    """Project either input event onto a translatable request; None if neither.

    For a recognized sign the translatable content is the **gloss**, falling back to the
    phrase ``label`` when the recognizer emitted no gloss. Both are placeholder content
    until ADR-0002's consultation; either way it is the recognized sign, not the phrase
    id used as an internal key.
    """
    if isinstance(model, TranscriptSegment):
        source = language.normalize(model.language) or language.normalize(
            settings.default_source_language
        )
        return _TextRequest(model.session_id, model.segment_id, model.text, source)
    if isinstance(model, SignRecognitionResult):
        gloss = (model.gloss or model.label).strip()
        return _TextRequest(
            model.session_id,
            model.segment_id,
            gloss,
            language.normalize(settings.sign_gloss_source_language),
        )
    return None


class TranslationPipeline(BaseInferencePipeline):
    output_channel = AccessibilityChannel.TRANSLATION
    usage_unit = "translation"

    def __init__(self, settings: Settings) -> None:
        super().__init__(
            settings, topics=["ai.transcript.segment", "ai.sign.recognition.result"]
        )
        self.target = language.normalize(settings.default_target_language)
        self.engine = TranslationEngine(settings)

    async def on_start(self) -> None:
        self.engine.load()
        # Honest readiness: a requested real model that failed to load turns
        # /readyz to 503 under REQUIRE_MODEL (see BaseInferencePipeline).
        self.model_ready = self.engine.ready

    async def handle(self, event_key: str, model: BaseModel) -> None:
        request = _as_request(model, self.settings)
        if request is None:
            return
        # Preference gate: skip when no participant in the session wants translation.
        if not self.should_generate(request.session_id):
            return
        translated = self.engine.translate(
            request.text, source=request.source_language, target=self.target
        )
        result = to_result(
            request.session_id,
            request.segment_id,
            request.text,
            translated,
            source=request.source_language,
            target=self.target,
        )
        await self.publish("ai.translation.result", result, key=request.session_id)
