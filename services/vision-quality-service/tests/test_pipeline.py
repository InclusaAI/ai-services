from __future__ import annotations

from inclusaai_contracts import schema_registry
from inclusaai_contracts.events import VideoFrame

from app.config import Settings
from app.inference.engine import VisionQualityEngine
from app.pipeline import VisionQualityPipeline
from app.postprocessing import to_signal


def test_engine_assesses(settings: Settings, video_frame: VideoFrame) -> None:
    import base64

    engine = VisionQualityEngine(settings)
    engine.load()
    assessment = engine.assess(base64.b64decode(video_frame.payload_b64))
    assert assessment.signing_pace == "ok"


def test_to_signal_is_contract_valid(settings: Settings, video_frame: VideoFrame) -> None:
    import base64

    engine = VisionQualityEngine(settings)
    engine.load()
    assessment = engine.assess(base64.b64decode(video_frame.payload_b64))
    signal = to_signal(video_frame, assessment)
    validated = schema_registry.validate("ai.vision.quality.signal", signal.model_dump())
    assert validated.session_id == "s1"
    assert validated.presenter_id == "presenter1"


async def test_handle_publishes(settings: Settings, video_frame: VideoFrame, monkeypatch) -> None:
    pipeline = VisionQualityPipeline(settings)
    pipeline.engine.load()
    published: list[tuple[str, object]] = []

    async def fake_publish(event_key, payload, *, key=None):  # noqa: ANN001, ANN202
        published.append((event_key, payload))

    monkeypatch.setattr(pipeline, "publish", fake_publish)
    await pipeline.handle("media.video.frame", video_frame)
    assert published and published[0][0] == "ai.vision.quality.signal"
