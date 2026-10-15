"""sign-recognition pipeline tests.

These are **mediapipe-free**: they target a *known* stub code via
``inclusaai_pose_tools.pose_for_code`` (guaranteeing the test helper and the engine
agree by construction), drive the rule-based fingerspelling classifier with
synthetic handshape poses (``tests/handshapes.py``), and exercise the offline
degrade path of ``extract_landmarks`` (no MediaPipe/opencv needed). The real
MediaPipe extraction path is smoke-tested separately, gated behind
``SIGN_RUN_MEDIAPIPE_TESTS=1`` (mirrors asr's ``ASR_RUN_WHISPER_TESTS``).
"""

from __future__ import annotations

import os
from typing import Any

import pytest
from app.config import Settings
from app.detection import extract_landmarks
from app.inference.engine import SignEngine
from app.pipeline import SignPipeline
from app.postprocessing import to_result
from app.preprocessing import decode_frame
from inclusaai_contracts import schema_registry
from inclusaai_contracts.events import (
    AccessibilityChannel,
    AccessibilityPreferenceUpdated,
    VideoFrame,
)
from inclusaai_pose_tools import frame_count, pose_for_code, pose_to_keypoints
from inclusaai_sign_vocab import FINGERSPELL_ALPHABET, NUM_KEYPOINTS, phrase_ids

from tests.handshapes import handshape_pose

_ALLOWED_LABELS = set(phrase_ids()) | set(FINGERSPELL_ALPHABET)


def test_engine_stub_recognizes(settings: Settings) -> None:
    engine = SignEngine(settings)
    engine.load()
    out = engine.recognize(pose_for_code(1))  # no hand -> phrase stub path
    assert out and out[0].label in phrase_ids()


def test_stub_only_emits_closed_set_labels(settings: Settings) -> None:
    """Matched-pair enforcement (recognition side): every label the offline engine
    can emit is a closed-set phrase id or a fingerspelling letter — never anything
    the avatar couldn't also produce (ADR-0002 symmetric vocabulary)."""
    engine = SignEngine(settings)
    engine.load()
    for code in range(200):
        recognition = engine.recognize(pose_for_code(code))[0]
        assert recognition.label in _ALLOWED_LABELS, f"code {code} -> {recognition.label!r}"
        if recognition.is_fingerspelling:
            assert recognition.label in FINGERSPELL_ALPHABET


def test_real_fingerspelling_path(settings: Settings) -> None:
    """A posed handshape resolves to a REAL letter, not the phrase stub."""
    engine = SignEngine(settings)
    engine.load()
    recognition = engine.recognize(handshape_pose("v"))[0]
    assert recognition.is_fingerspelling
    assert recognition.label == "v"
    assert recognition.gloss == "V"


def test_fingerspelling_falls_back_to_phrase_when_hand_absent(
    settings: Settings,
) -> None:
    """A frame with no usable hand takes the closed-set phrase path."""
    engine = SignEngine(settings)
    engine.load()
    recognition = engine.recognize(pose_for_code(0))[0]
    assert not recognition.is_fingerspelling
    assert recognition.label in phrase_ids()


def test_empty_frame_is_not_recognized(settings: Settings) -> None:
    """Empty frame bytes -> no pose -> nothing recognized (no phantom emissions)."""
    engine = SignEngine(settings)
    engine.load()
    assert extract_landmarks(b"") is None
    assert engine.recognize(None) == []


def test_offline_extraction_yields_a_recognizable_pose(
    settings: Settings, video_frame: VideoFrame
) -> None:
    """With MediaPipe absent (or the frame undecodable), extraction still degrades to a
    full 51-point pose so the pipeline is exercisable offline, and the engine maps it to
    a closed-set label."""
    pose = extract_landmarks(decode_frame(video_frame))
    assert pose is not None
    assert frame_count(pose) >= 1
    assert len(pose_to_keypoints(pose, 0)) == NUM_KEYPOINTS
    engine = SignEngine(settings)
    engine.load()
    assert engine.recognize(pose)[0].label in _ALLOWED_LABELS


def test_window_majority_vote(settings: Settings) -> None:
    """A window's label is the per-frame majority — one minority frame can't flip it."""
    engine = SignEngine(settings)
    engine.load()
    out = engine.recognize_window(
        [handshape_pose("v"), handshape_pose("v"), handshape_pose("a")]
    )
    assert len(out) == 1
    assert out[0].label == "v"
    assert out[0].is_fingerspelling
    assert out[0].confidence == pytest.approx(0.9)


def test_window_votes_phrase_labels_too(settings: Settings) -> None:
    engine = SignEngine(settings)
    engine.load()
    pose = pose_for_code(3)
    out = engine.recognize_window([pose, pose])
    assert len(out) == 1
    assert out[0].label == engine.recognize(pose)[0].label
    assert not out[0].is_fingerspelling


def test_empty_window_emits_nothing(settings: Settings) -> None:
    engine = SignEngine(settings)
    engine.load()
    assert engine.recognize_window([]) == []


def test_to_result_is_contract_valid(settings: Settings, video_frame: VideoFrame) -> None:
    engine = SignEngine(settings)
    engine.load()
    recognition = engine.recognize(pose_for_code(1))[0]
    result = to_result(video_frame, recognition, settings.sign_language)
    validated = schema_registry.validate("ai.sign.recognition.result", result.model_dump())
    assert validated.session_id == "s1"
    assert validated.sign_language == "ASL"


def test_to_result_spans_window(settings: Settings, video_frame: VideoFrame) -> None:
    """A windowed result spans first-to-last frame timestamps."""
    engine = SignEngine(settings)
    engine.load()
    recognition = engine.recognize(handshape_pose("b"))[0]
    result = to_result(
        video_frame, recognition, settings.sign_language, start_ms=1000, end_ms=1400
    )
    assert result.start_ms == 1000
    assert result.end_ms == 1400


async def test_handle_buffers_until_window_full(
    settings: Settings, video_frame: VideoFrame, monkeypatch
) -> None:
    pipeline = SignPipeline(settings)
    pipeline.engine.load()
    published: list[tuple[str, object]] = []

    async def fake_publish(event_key, payload, *, key=None):  # noqa: ANN001, ANN202
        published.append((event_key, payload))

    monkeypatch.setattr(pipeline, "publish", fake_publish)
    settings.gesture_window_frames = 3

    await pipeline.handle("media.video.frame", video_frame)  # 1/3
    await pipeline.handle("media.video.frame", video_frame)  # 2/3
    assert not published, "no publish before the gesture window is full"

    await pipeline.handle("media.video.frame", video_frame)  # 3/3 -> classify
    assert len(published) == 1
    assert published[0][0] == "ai.sign.recognition.result"


async def test_handle_separates_sessions(
    settings: Settings, video_frame: VideoFrame, monkeypatch
) -> None:
    """Frames from different sessions buffer independently."""
    pipeline = SignPipeline(settings)
    pipeline.engine.load()
    settings.gesture_window_frames = 2
    published: list[tuple[str, Any]] = []

    async def fake_publish(event_key, payload, *, key=None):  # noqa: ANN001, ANN202
        published.append((event_key, payload))

    monkeypatch.setattr(pipeline, "publish", fake_publish)

    other = video_frame.model_copy(update={"session_id": "s2"})
    await pipeline.handle("media.video.frame", video_frame)  # s1: 1/2
    await pipeline.handle("media.video.frame", other)  # s2: 1/2
    assert not published

    await pipeline.handle("media.video.frame", video_frame)  # s1: 2/2 -> publish
    assert len(published) == 1
    assert published[0][1].session_id == "s1"


# ------------------------------------------------------------------ preference gate
def _prefs(pipeline: SignPipeline, session_id: str, participant: str, *channels: str) -> None:
    pipeline.preferences.update(
        AccessibilityPreferenceUpdated(
            session_id=session_id,
            participant_id=participant,
            channels=[AccessibilityChannel(c) for c in channels],
            updated_at_ms=0,
        )
    )


def test_pipeline_is_gated_on_captions_and_translation() -> None:
    """Recognition feeds BOTH channels, so the gate must be "any of", not "one of"."""
    assert SignPipeline.output_channels == (
        AccessibilityChannel.CAPTIONS,
        AccessibilityChannel.TRANSLATION,
    )


async def test_handle_skips_a_session_nobody_is_reading(
    settings: Settings, video_frame: VideoFrame, monkeypatch
) -> None:
    """Nobody needs captions or translation -> skip the work entirely (the TODO(gating))."""
    pipeline = SignPipeline(settings)
    pipeline.engine.load()
    settings.gesture_window_frames = 2
    published: list[tuple[str, Any]] = []

    async def fake_publish(event_key, payload, *, key=None):  # noqa: ANN001, ANN202
        published.append((event_key, payload))

    monkeypatch.setattr(pipeline, "publish", fake_publish)
    _prefs(pipeline, "s1", "p1", "avatar")  # a channel recognition does not serve
    await pipeline.handle("media.video.frame", video_frame)
    await pipeline.handle("media.video.frame", video_frame)
    assert not published
    assert not pipeline._windows  # gated before any pose was even extracted


async def test_handle_runs_when_either_channel_is_needed(
    settings: Settings, video_frame: VideoFrame, monkeypatch
) -> None:
    """A single-channel check would gate this off and drop needed output."""
    settings.gesture_window_frames = 2
    for channel in ("captions", "translation"):
        assert await _window_publishes(settings, video_frame, monkeypatch, channel) == 1


async def _window_publishes(
    settings: Settings,
    video_frame: VideoFrame,
    monkeypatch: Any,
    channel: str | None,
) -> int:
    """Feed one full gesture window for a session with ``channel`` enabled.

    ``channel=None`` means no preference data at all (the fail-open path). Returns how
    many results were published.
    """
    pipeline = SignPipeline(settings)
    pipeline.engine.load()
    published: list[tuple[str, Any]] = []

    async def fake_publish(event_key, payload, *, key=None):  # noqa: ANN001, ANN202
        published.append((event_key, payload))

    monkeypatch.setattr(pipeline, "publish", fake_publish)
    if channel is not None:
        _prefs(pipeline, "s1", "p1", channel)
    await pipeline.handle("media.video.frame", video_frame)
    await pipeline.handle("media.video.frame", video_frame)
    return len(published)


async def test_handle_fails_open_before_preferences_arrive(
    settings: Settings, video_frame: VideoFrame, monkeypatch
) -> None:
    """No preference data yet -> generate, so the propagation race never drops output."""
    settings.gesture_window_frames = 2
    assert await _window_publishes(settings, video_frame, monkeypatch, None) == 1


async def test_gating_drops_a_partial_window(
    settings: Settings, video_frame: VideoFrame, monkeypatch
) -> None:
    """A session gated off mid-window must not resume on stale poses when re-enabled."""
    pipeline = SignPipeline(settings)
    pipeline.engine.load()
    settings.gesture_window_frames = 3
    published: list[tuple[str, Any]] = []

    async def fake_publish(event_key, payload, *, key=None):  # noqa: ANN001, ANN202
        published.append((event_key, payload))

    monkeypatch.setattr(pipeline, "publish", fake_publish)
    await pipeline.handle("media.video.frame", video_frame)  # 1/3 buffered
    assert "s1" in pipeline._windows

    _prefs(pipeline, "s1", "p1", "avatar")  # nobody reading -> gate off
    await pipeline.handle("media.video.frame", video_frame)
    assert "s1" not in pipeline._windows, "partial window must be dropped when gated off"

    # re-enabled: a full fresh window is needed again, so 2 frames must not publish.
    pipeline.preferences.remove_participant("s1", "p1")
    await pipeline.handle("media.video.frame", video_frame)
    await pipeline.handle("media.video.frame", video_frame)
    assert not published, "must re-buffer a whole window, not resume the stale one"


# ----------------------------------------------------------------- window eviction
async def test_window_cache_is_bounded(
    settings: Settings, video_frame: VideoFrame, monkeypatch
) -> None:
    """Every session the broker fans out is buffered; the cache must not grow forever."""
    pipeline = SignPipeline(settings)
    pipeline.engine.load()
    settings.gesture_window_frames = 10  # never fills -> every session stays resident
    settings.max_gesture_sessions = 3

    async def fake_publish(event_key, payload, *, key=None):  # noqa: ANN001, ANN202
        return None

    monkeypatch.setattr(pipeline, "publish", fake_publish)

    for i in range(10):
        frame = video_frame.model_copy(update={"session_id": f"s{i}"})
        await pipeline.handle("media.video.frame", frame)

    assert len(pipeline._windows) == settings.max_gesture_sessions
    # least-recently-seen evicted: the newest sessions survive, the oldest do not.
    assert "s9" in pipeline._windows
    assert "s0" not in pipeline._windows


async def test_active_window_is_not_evicted_under_pressure(
    settings: Settings, video_frame: VideoFrame, monkeypatch
) -> None:
    """A session still being framed must survive the churn of other sessions."""
    pipeline = SignPipeline(settings)
    pipeline.engine.load()
    settings.gesture_window_frames = 1000
    settings.max_gesture_sessions = 2

    async def fake_publish(event_key, payload, *, key=None):  # noqa: ANN001, ANN202
        return None

    monkeypatch.setattr(pipeline, "publish", fake_publish)
    hot = video_frame.model_copy(update={"session_id": "hot"})
    for i in range(10):
        # interleave: "hot" is the most recently seen session every single round.
        await pipeline.handle("media.video.frame", hot)
        await pipeline.handle(
            "media.video.frame", video_frame.model_copy(update={"session_id": f"cold{i}"})
        )
    assert "hot" in pipeline._windows
    assert len(pipeline._windows) == settings.max_gesture_sessions


@pytest.mark.skipif(
    os.environ.get("SIGN_RUN_MEDIAPIPE_TESTS") != "1",
    reason="set SIGN_RUN_MEDIAPIPE_TESTS=1 to run the real MediaPipe extraction smoke test",
)
def test_real_mediapipe_extraction_smoke() -> None:
    """Real path: encode an image, run it through MediaPipe Holistic, and confirm a
    51-point skeleton pose comes back. A blank image detects no person (all-zero pose),
    which is still a valid pose — this smokes the imdecode -> load_holistic ->
    holistic_to_skeleton plumbing, not detection quality."""
    import cv2
    import numpy as np

    blank = np.zeros((64, 64, 3), dtype=np.uint8)
    ok, buffer = cv2.imencode(".jpg", blank)
    assert ok
    pose = extract_landmarks(buffer.tobytes())
    assert pose is not None
    assert frame_count(pose) == 1
    assert len(pose_to_keypoints(pose, 0)) == NUM_KEYPOINTS
