"""Kafka event payload models — the single source of truth for this repo.

PLACEHOLDER for @inclusaai/kafka-contracts. All topic payloads that ai-services
consumes or publishes are modelled here as pydantic v2 models. JSON Schemas are
*derived* from these (see schema_registry + scripts/gen_contracts.py) so the two
representations can never drift.

Topic names (the wire addresses these payloads travel on) live in
inclusaai_kafka_clients.topics, not here.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# Shared enums
# --------------------------------------------------------------------------- #
class AccessibilityChannel(StrEnum):
    """Output channels a participant may need. Drives preference-aware gating:
    ai-services skips generating an output no active participant has enabled
    (see ai-services-IMPLEMENTATION.md §5/§9)."""

    CAPTIONS = "captions"
    AVATAR = "avatar"
    GESTURES = "gestures"
    TRANSLATION = "translation"
    TTS = "tts"


# --------------------------------------------------------------------------- #
# INBOUND — consumed by ai-services
# --------------------------------------------------------------------------- #
class AudioChunk(BaseModel):
    """`media.session.<id>.audio.chunk` — from realtime-media-backend."""

    session_id: str
    speaker_id: str
    sequence: int
    timestamp_ms: int
    sample_rate: int = 16000
    encoding: str = "opus"  # or "pcm_s16le"
    payload_b64: str = Field(description="base64-encoded audio bytes (placeholder transport)")


class VideoFrame(BaseModel):
    """`media.session.<id>.video.frame` — from realtime-media-backend.

    Sampled at ~15fps by default (ADR-0007), not full framerate."""

    session_id: str
    presenter_id: str
    sequence: int
    timestamp_ms: int
    width: int
    height: int
    fps: int = 15  # ADR-0007 starting point
    payload_b64: str = Field(description="base64-encoded frame, e.g. JPEG (placeholder transport)")


class ParticipantEvent(BaseModel):
    """`media.session.<id>.participant.joined` / `.left`."""

    session_id: str
    participant_id: str
    event: str  # "joined" | "left"
    timestamp_ms: int


class AccessibilityPreferenceUpdated(BaseModel):
    """`accessibility.preference.updated` — from platform-backend.

    The event ai-services cares most about: it determines which downstream
    outputs actually need generating per participant."""

    session_id: str
    participant_id: str
    channels: list[AccessibilityChannel] = Field(default_factory=list)
    caption_language: str | None = None
    translation_target_language: str | None = None
    sign_language: str = "ASL"  # ASL only for MVP (ADR-0002)
    updated_at_ms: int


# --------------------------------------------------------------------------- #
# OUTBOUND — published by ai-services
# --------------------------------------------------------------------------- #
class TranscriptSegment(BaseModel):
    """`ai.transcript.segment` — from asr-service."""

    session_id: str
    speaker_id: str
    segment_id: str
    text: str
    start_ms: int
    end_ms: int
    language: str = "en"
    is_final: bool = True
    confidence: float | None = None


class SignRecognitionResult(BaseModel):
    """`ai.sign.recognition.result` — from sign-recognition-service.

    Closed-set classification against the same constrained vocabulary the avatar
    generates from, plus fingerspelling for out-of-vocabulary content (ADR-0002)."""

    session_id: str
    signer_id: str
    segment_id: str
    label: str
    gloss: str | None = None
    is_fingerspelling: bool = False
    start_ms: int
    end_ms: int
    confidence: float | None = None
    sign_language: str = "ASL"


class TranslationResult(BaseModel):
    """`ai.translation.result` — from translation-service."""

    session_id: str
    segment_id: str
    source_language: str
    target_language: str
    source_text: str
    translated_text: str


class TtsAudioChunk(BaseModel):
    """`ai.tts.audio.chunk` — from tts-service (Deaf->Hearing direction)."""

    session_id: str
    target_participant_id: str | None = None
    sequence: int
    timestamp_ms: int
    sample_rate: int = 24000
    encoding: str = "pcm_s16le"
    language: str = "en"
    payload_b64: str


class PoseKeypoint(BaseModel):
    x: float
    y: float
    z: float = 0.0
    visibility: float = 1.0


class AvatarPoseFrame(BaseModel):
    """`ai.avatar.pose.frame` — from avatar-pose-service.

    The highest-frequency, most bandwidth-sensitive schema in the whole platform
    (IMPLEMENTATION §5). Version carefully and load-test the fan-out path.
    One skeletal pose frame, generated from a constrained-vocabulary phrase."""

    session_id: str
    phrase_id: str | None = Field(
        default=None, description="id in the constrained-vocabulary library (ADR-0002)"
    )
    frame_index: int
    timestamp_ms: int
    fps: int = 30
    keypoints: list[PoseKeypoint]


class VisionQualitySignal(BaseModel):
    """`ai.vision.quality.signal` — from vision-quality-service; feeds presenter-assist."""

    session_id: str
    presenter_id: str
    timestamp_ms: int
    framing_ok: bool | None = None
    lighting_ok: bool | None = None
    hand_visibility_ok: bool | None = None
    signing_pace: str | None = None  # "slow" | "ok" | "fast"
    recommendation: str | None = None


class EngagementSignalAggregate(BaseModel):
    """`ai.engagement.signal.aggregate` — from engagement-service.

    PRIVACY-CRITICAL (IMPLEMENTATION §2): this schema STRUCTURALLY excludes any
    per-individual identifier — there is intentionally NO participant_id/user_id
    field, and adding one would be a contract violation, not just a policy one.
    Only session-level aggregates over a time window are ever carried."""

    session_id: str
    window_start_ms: int
    window_end_ms: int
    participant_count: int
    attention_score: float | None = None  # aggregate 0..1
    reaction_counts: dict[str, int] = Field(default_factory=dict)


class UsageAggregate(BaseModel):
    """`ai.usage.aggregate` — periodic aggregated usage counts for billing (ADR-0009).

    Published periodically by every inference service, NOT one event per inference —
    billing needs periodic counts, not the raw firehose."""

    service_name: str
    session_id: str | None = None
    window_start_ms: int
    window_end_ms: int
    unit: str  # e.g. "transcript_segment", "avatar_pose_frame", "audio_second"
    count: int
