"""sign-recognition pipeline tests.

These are **mediapipe-free**: they target a *known* stub code via
``inclusaai_pose_tools.pose_for_code`` (guaranteeing the test helper and the engine
agree by construction) and exercise the offline degrade path of ``extract_landmarks``
(no MediaPipe/opencv needed). The real MediaPipe extraction path is smoke-tested
separately, gated behind ``SIGN_RUN_MEDIAPIPE_TESTS=1`` (mirrors asr's
``ASR_RUN_WHISPER_TESTS``).
"""

from __future__ import annotations

import os

import pytest
from app.config import Settings
from app.detection import extract_landmarks
from app.inference.engine import SignEngine
from app.pipeline import SignPipeline
from app.postprocessing import to_result
from app.preprocessing import decode_frame
from inclusaai_contracts import schema_registry
from inclusaai_contracts.events import VideoFrame
from inclusaai_pose_tools import frame_count, pose_for_code, pose_to_keypoints
from inclusaai_sign_vocab import FINGERSPELL_ALPHABET, NUM_KEYPOINTS, phrase_ids

_ALLOWED_LABELS = set(phrase_ids()) | set(FINGERSPELL_ALPHABET)


def test_engine_stub_recognizes(settings: Settings) -> None:
    engine = SignEngine(settings)
    engine.load()
    out = engine.recognize(pose_for_code(1))  # code 1: not a fingerspell multiple
    assert out and out[0].label


def test_stub_only_emits_closed_set_labels(settings: Settings) -> None:
    """Matched-pair enforcement (recognition side): every label the stub can emit is
    a closed-set phrase id or a fingerspelling letter — never anything the avatar
    couldn't also produce (ADR-0002 symmetric vocabulary)."""
    engine = SignEngine(settings)
    engine.load()
    for code in range(200):
        recognition = engine.recognize(pose_for_code(code))[0]
        assert recognition.label in _ALLOWED_LABELS, f"code {code} -> {recognition.label!r}"
        if recognition.is_fingerspelling:
            assert recognition.label in FINGERSPELL_ALPHABET


def test_fingerspelling_path_is_reachable(settings: Settings) -> None:
    engine = SignEngine(settings)
    engine.load()
    recognition = engine.recognize(pose_for_code(0))[0]  # code 0 routes to the fallback
    assert recognition.is_fingerspelling
    assert recognition.label in FINGERSPELL_ALPHABET


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


def test_to_result_is_contract_valid(settings: Settings, video_frame: VideoFrame) -> None:
    engine = SignEngine(settings)
    engine.load()
    recognition = engine.recognize(pose_for_code(1))[0]
    result = to_result(video_frame, recognition, settings.sign_language)
    validated = schema_registry.validate("ai.sign.recognition.result", result.model_dump())
    assert validated.session_id == "s1"
    assert validated.sign_language == "ASL"


async def test_handle_publishes(settings: Settings, video_frame: VideoFrame, monkeypatch) -> None:
    pipeline = SignPipeline(settings)
    pipeline.engine.load()
    published: list[tuple[str, object]] = []

    async def fake_publish(event_key, payload, *, key=None):  # noqa: ANN001, ANN202
        published.append((event_key, payload))

    monkeypatch.setattr(pipeline, "publish", fake_publish)
    await pipeline.handle("media.video.frame", video_frame)
    assert published and published[0][0] == "ai.sign.recognition.result"


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
