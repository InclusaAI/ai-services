from __future__ import annotations

import base64

from inclusaai_contracts import schema_registry
from inclusaai_contracts.events import VideoFrame

from app.config import Settings
from app.detection import extract_landmarks
from app.inference.engine import SignEngine
from app.pipeline import SignPipeline
from app.postprocessing import to_result
from app.preprocessing import decode_frame


def test_engine_stub_recognizes(settings: Settings, video_frame: VideoFrame) -> None:
    engine = SignEngine(settings)
    engine.load()
    landmarks = extract_landmarks(decode_frame(video_frame))
    out = engine.recognize(landmarks)
    assert out and out[0].label


def test_to_result_is_contract_valid(settings: Settings, video_frame: VideoFrame) -> None:
    engine = SignEngine(settings)
    engine.load()
    landmarks = extract_landmarks(base64.b64decode(video_frame.payload_b64))
    recognition = engine.recognize(landmarks)[0]
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
