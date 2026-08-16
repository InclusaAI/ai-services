from __future__ import annotations

from app.config import Settings
from app.inference.engine import PoseEngine
from app.pipeline import AvatarPosePipeline
from app.postprocessing import to_frames
from inclusaai_contracts import schema_registry
from inclusaai_contracts.events import TranscriptSegment


def test_engine_generates_frames(settings: Settings) -> None:
    engine = PoseEngine(settings)
    engine.load()
    phrase_id, frames = engine.generate("hello there")
    assert frames  # a pose sequence
    assert phrase_id == "hello"


def test_to_frames_are_contract_valid(settings: Settings, transcript: TranscriptSegment) -> None:
    engine = PoseEngine(settings)
    engine.load()
    phrase_id, frames = engine.generate(transcript.text)
    pose_frames = to_frames(transcript, phrase_id, frames, settings.fps)
    assert pose_frames
    for frame in pose_frames:
        validated = schema_registry.validate("ai.avatar.pose.frame", frame.model_dump())
        assert validated.session_id == "s1"


async def test_handle_publishes_when_ungated(
    settings: Settings, transcript: TranscriptSegment, monkeypatch
) -> None:
    pipeline = AvatarPosePipeline(settings)
    pipeline.engine.load()
    published: list[tuple[str, object]] = []

    async def fake_publish(event_key, payload, *, key=None):  # noqa: ANN001, ANN202
        published.append((event_key, payload))

    monkeypatch.setattr(pipeline, "publish", fake_publish)
    await pipeline.handle("ai.transcript.segment", transcript)
    assert published and published[0][0] == "ai.avatar.pose.frame"
