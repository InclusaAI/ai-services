"""asr-service pipeline: ``media.*.audio.chunk`` -> ``ai.transcript.segment``.

Subclasses the shared BaseInferencePipeline, which already provides the Kafka
consume loop, preference cache, scaling gauges, usage aggregation, and graceful
shutdown. This class only supplies the ASR-specific bits: what to subscribe to,
how to load the model, and how to turn one input event into output event(s).
"""

from __future__ import annotations

from pydantic import BaseModel

from inclusaai_ai_core import BaseInferencePipeline
from inclusaai_contracts.events import AudioChunk
from inclusaai_kafka_clients.topics import AUDIO_CHUNK_SUBSCRIPTION

from app.config import Settings
from app.inference.engine import AsrEngine
from app.postprocessing.segments import to_segment
from app.preprocessing.audio import decode_audio


class AsrPipeline(BaseInferencePipeline):
    # Transcripts feed captions AND every downstream channel (translation, tts,
    # avatar), so this output is foundational and NOT preference-gated. Leaf
    # services gate their own channel-specific outputs.
    output_channel = None
    usage_unit = "transcript_segment"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings, subscription=AUDIO_CHUNK_SUBSCRIPTION)
        self.language = settings.transcript_language
        self.engine = AsrEngine(settings)

    async def on_start(self) -> None:
        self.engine.load()

    async def handle(self, event_key: str, model: BaseModel) -> None:
        if not isinstance(model, AudioChunk):
            return
        pcm = decode_audio(model)
        transcriptions = self.engine.transcribe(
            pcm, sample_rate=model.sample_rate, base_ms=model.timestamp_ms
        )
        for transcription in transcriptions:
            segment = to_segment(model, transcription, self.language)
            # key by session so a session's segments stay ordered on one partition.
            await self.publish("ai.transcript.segment", segment, key=model.session_id)
