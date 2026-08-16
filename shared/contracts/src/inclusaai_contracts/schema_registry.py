"""Map logical event keys to their payload models, with schema/validation helpers.

The event key is a stable, transport-independent identifier. The Kafka topic
NAME a payload travels on is defined separately in
``inclusaai_kafka_clients.topics`` (some keys, e.g. media.* , are per-session
topic patterns).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from inclusaai_contracts import events

EVENT_MODELS: dict[str, type[BaseModel]] = {
    # inbound
    "media.audio.chunk": events.AudioChunk,
    "media.video.frame": events.VideoFrame,
    "media.participant": events.ParticipantEvent,
    "accessibility.preference.updated": events.AccessibilityPreferenceUpdated,
    # outbound
    "ai.transcript.segment": events.TranscriptSegment,
    "ai.sign.recognition.result": events.SignRecognitionResult,
    "ai.translation.result": events.TranslationResult,
    "ai.tts.audio.chunk": events.TtsAudioChunk,
    "ai.avatar.pose.frame": events.AvatarPoseFrame,
    "ai.vision.quality.signal": events.VisionQualitySignal,
    "ai.engagement.signal.aggregate": events.EngagementSignalAggregate,
    "ai.usage.aggregate": events.UsageAggregate,
}


def model_for(event_key: str) -> type[BaseModel]:
    try:
        return EVENT_MODELS[event_key]
    except KeyError as exc:
        known = ", ".join(sorted(EVENT_MODELS))
        raise KeyError(f"Unknown event key {event_key!r}. Known keys: {known}") from exc


def json_schema(event_key: str) -> dict[str, Any]:
    """JSON Schema for an event, derived from its pydantic model."""
    return model_for(event_key).model_json_schema()


def validate(event_key: str, payload: dict[str, Any]) -> BaseModel:
    """Validate a raw payload dict against its model, returning the parsed model."""
    return model_for(event_key).model_validate(payload)
