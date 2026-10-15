from __future__ import annotations

from app.config import Settings
from app.inference.engine import PoseEngine
from app.pipeline import AvatarPosePipeline
from app.postprocessing import to_frames
from app.vocabulary import pose_for
from inclusaai_contracts import schema_registry
from inclusaai_contracts.events import AudioChunk, TranscriptSegment, TranslationResult
from inclusaai_pose_tools import frame_count, pose_to_keypoints
from inclusaai_sign_vocab import NUM_KEYPOINTS, PHRASE_BY_ID, phrase_ids
from inclusaai_utils import now_ms


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
    pose_frames = to_frames(
        transcript.session_id, transcript.start_ms, phrase_id, pose, settings.fps
    )
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


def test_pipeline_subscribes_to_both_text_inputs() -> None:
    """Both legs of the round trip: speech->avatar and the Deaf-presenter leg."""
    pipeline = AvatarPosePipeline(Settings(service_name="t", kafka_bootstrap_servers=""))
    assert sorted(pipeline._topics) == ["ai.transcript.segment", "ai.translation.result"]


# ------------------------------------------------------- ai.translation.result leg
async def test_handle_consumes_translation_result(
    settings: Settings, translation: TranslationResult, monkeypatch
) -> None:
    """The Deaf-presenter leg publishes pose frames (ai-services-IMPLEMENTATION §map)."""
    pipeline = AvatarPosePipeline(settings)
    pipeline.engine.load()
    published: list[tuple[str, object]] = []

    async def fake_publish(event_key, payload, *, key=None):  # noqa: ANN001, ANN202
        published.append((event_key, payload))

    monkeypatch.setattr(pipeline, "publish", fake_publish)
    await pipeline.handle("ai.translation.result", translation)
    assert published
    assert {key for key, _ in published} == {"ai.avatar.pose.frame"}
    assert all(frame.session_id == "s1" for _, frame in published)


async def test_translation_path_signs_the_target_language(
    settings: Settings, translation: TranslationResult, monkeypatch
) -> None:
    """The avatar signs ``translated_text`` — never ``source_text`` (the sign gloss)."""
    pipeline = AvatarPosePipeline(settings)
    pipeline.engine.load()
    published: list[tuple[str, object]] = []

    async def fake_publish(event_key, payload, *, key=None):  # noqa: ANN001, ANN202
        published.append((event_key, payload))

    monkeypatch.setattr(pipeline, "publish", fake_publish)
    await pipeline.handle("ai.translation.result", translation)
    # "HELLO" (source_text) and "hello" (translated_text) both normalize to the same
    # phrase id, so assert the path explicitly with text that distinguishes them.
    phrase_id, _ = pipeline.engine.generate(translation.translated_text)
    assert all(frame.phrase_id == phrase_id for _, frame in published)

    published.clear()
    off_vocab = translation.model_copy(
        update={"source_text": "WXYZ", "translated_text": "hello"}
    )
    await pipeline.handle("ai.translation.result", off_vocab)
    assert published and published[0][1].phrase_id == "hello"


async def test_translation_frames_anchor_on_arrival_time(
    settings: Settings, translation: TranslationResult, monkeypatch
) -> None:
    """TranslationResult carries no timing, so frames anchor on wall clock (now_ms)."""
    pipeline = AvatarPosePipeline(settings)
    pipeline.engine.load()
    published: list[tuple[str, object]] = []

    async def fake_publish(event_key, payload, *, key=None):  # noqa: ANN001, ANN202
        published.append((event_key, payload))

    monkeypatch.setattr(pipeline, "publish", fake_publish)
    before = now_ms()
    await pipeline.handle("ai.translation.result", translation)
    stamps = [frame.timestamp_ms for _, frame in published]
    assert stamps and min(stamps) >= before - 1000  # wall clock, not the source segment


async def test_transcript_frames_still_anchor_on_the_segment_start(
    settings: Settings, transcript: TranscriptSegment, monkeypatch
) -> None:
    """The transcript leg keeps its source timing — the refactor must not break it."""
    pipeline = AvatarPosePipeline(settings)
    pipeline.engine.load()
    published: list[tuple[str, object]] = []

    async def fake_publish(event_key, payload, *, key=None):  # noqa: ANN001, ANN202
        published.append((event_key, payload))

    monkeypatch.setattr(pipeline, "publish", fake_publish)
    await pipeline.handle("ai.transcript.segment", transcript)
    assert published and published[0][1].timestamp_ms == transcript.start_ms


async def test_unrelated_events_are_ignored(settings: Settings, monkeypatch) -> None:
    pipeline = AvatarPosePipeline(settings)
    pipeline.engine.load()
    published: list[tuple[str, object]] = []

    async def fake_publish(event_key, payload, *, key=None):  # noqa: ANN001, ANN202
        published.append((event_key, payload))

    monkeypatch.setattr(pipeline, "publish", fake_publish)
    await pipeline.handle("ai.usage.aggregate", AudioChunk(
        session_id="s1", speaker_id="spk", sequence=0, timestamp_ms=0, payload_b64=""
    ))
    assert not published
