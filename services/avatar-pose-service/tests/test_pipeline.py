from __future__ import annotations

from app.config import Settings
from app.inference.engine import PoseEngine
from app.pipeline import AvatarPosePipeline
from app.postprocessing import to_frames
from app.vocabulary import pose_for
from inclusaai_contracts import schema_registry
from inclusaai_contracts.events import TranscriptSegment
from inclusaai_pose_tools import frame_count, pose_to_keypoints
from inclusaai_sign_vocab import NUM_KEYPOINTS, PHRASE_BY_ID, phrase_ids


def test_engine_generates_a_pose(settings: Settings) -> None:
    engine = PoseEngine(settings)
    engine.load()
    phrase_id, pose = engine.generate("hello there")
    assert phrase_id == "hello"
    assert frame_count(pose) > 1  # a multi-frame pose sequence
    assert len(pose_to_keypoints(pose, 0)) == NUM_KEYPOINTS  # full-skeleton keypoints per frame


def test_out_of_vocab_fingerspells(settings: Settings) -> None:
    engine = PoseEngine(settings)
    engine.load()
    phrase_id, pose = engine.generate("zzz")  # not in the closed vocabulary
    assert phrase_id is None  # no closed-set phrase matched
    assert frame_count(pose) >= 1  # ...but it still produces fingerspelled frames
    assert len(pose_to_keypoints(pose, 0)) == NUM_KEYPOINTS


def test_empty_text_is_neutral(settings: Settings) -> None:
    engine = PoseEngine(settings)
    engine.load()
    phrase_id, pose = engine.generate("   ")
    assert phrase_id is None
    assert frame_count(pose) == 1  # a single neutral resting frame


def test_every_phrase_has_a_pose() -> None:
    """Matched-pair enforcement (generation side): the avatar can render EVERY label
    the recognizer can emit — the symmetric-vocabulary guarantee of ADR-0002."""
    for phrase_id in phrase_ids():
        pose = pose_for(PHRASE_BY_ID[phrase_id])
        assert frame_count(pose) >= 1, f"no pose for {phrase_id}"
        assert len(pose_to_keypoints(pose, 0)) == NUM_KEYPOINTS


def test_to_frames_are_contract_valid(settings: Settings, transcript: TranscriptSegment) -> None:
    engine = PoseEngine(settings)
    engine.load()
    phrase_id, pose = engine.generate(transcript.text)
    pose_frames = to_frames(transcript, phrase_id, pose, settings.fps)
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
