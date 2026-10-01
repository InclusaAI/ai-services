"""Kafka topic names + the event-key <-> topic mapping.

Fixed topics (the ``ai.*`` outputs + the ``accessibility.preference.updated``
control topic) have stable names. The ``media.*`` inputs are **per-session**
topics (``media.session.<sessionId>.audio.chunk``), so services subscribe to them
by regex pattern rather than by a fixed name.

Ultimately these names are owned by @inclusaai/kafka-contracts; kept here in the
placeholder so producers/consumers agree.
"""

from __future__ import annotations

import re

# --- fixed AI output topics (event_key == topic name here) ---
AI_TOPICS: dict[str, str] = {
    "ai.transcript.segment": "ai.transcript.segment",
    "ai.sign.recognition.result": "ai.sign.recognition.result",
    "ai.translation.result": "ai.translation.result",
    "ai.tts.audio.chunk": "ai.tts.audio.chunk",
    "ai.avatar.pose.frame": "ai.avatar.pose.frame",
    "ai.vision.quality.signal": "ai.vision.quality.signal",
    "ai.engagement.signal.aggregate": "ai.engagement.signal.aggregate",
    "ai.usage.aggregate": "ai.usage.aggregate",
}

# --- fixed control topics consumed from platform-backend ---
CONTROL_TOPICS: dict[str, str] = {
    "accessibility.preference.updated": "accessibility.preference.updated",
}

# --- per-session media topic builders (from realtime-media-backend) ---
def audio_chunk_topic(session_id: str) -> str:
    return f"media.session.{session_id}.audio.chunk"


def video_frame_topic(session_id: str) -> str:
    return f"media.session.{session_id}.video.frame"


def participant_topic(session_id: str, event: str) -> str:
    """event is "joined" or "left"."""
    return f"media.session.{session_id}.participant.{event}"


# Regex subscription patterns for the media firehose (Kafka-side pattern subscribe).
AUDIO_CHUNK_SUBSCRIPTION = r"media\.session\..+\.audio\.chunk"
VIDEO_FRAME_SUBSCRIPTION = r"media\.session\..+\.video\.frame"
PARTICIPANT_SUBSCRIPTION = r"media\.session\..+\.participant\.(joined|left)"

_MEDIA_PATTERNS: dict[str, re.Pattern[str]] = {
    "media.audio.chunk": re.compile(r"^media\.session\.[^.]+\.audio\.chunk$"),
    "media.video.frame": re.compile(r"^media\.session\.[^.]+\.video\.frame$"),
    "media.participant": re.compile(r"^media\.session\.[^.]+\.participant\.(joined|left)$"),
}

_FIXED_REVERSE: dict[str, str] = {v: k for k, v in {**AI_TOPICS, **CONTROL_TOPICS}.items()}


def topic_for_event_key(event_key: str) -> str:
    """Resolve a fixed topic name for an event key. Media events are per-session —
    use ``audio_chunk_topic()`` / ``video_frame_topic()`` for those."""
    try:
        return {**AI_TOPICS, **CONTROL_TOPICS}[event_key]
    except KeyError as exc:
        raise KeyError(
            f"{event_key!r} has no fixed topic (media.* topics are per-session)."
        ) from exc


def topic_to_event_key(topic: str) -> str:
    """Reverse a concrete topic name back to its logical event key."""
    if topic in _FIXED_REVERSE:
        return _FIXED_REVERSE[topic]
    for event_key, pattern in _MEDIA_PATTERNS.items():
        if pattern.match(topic):
            return event_key
    raise KeyError(f"Cannot map topic {topic!r} to a known event key.")
