"""Pipeline wiring + contract conformance, all offline (stub engine)."""

from __future__ import annotations

import base64
from typing import Any

from app.config import Settings
from app.inference.engine import AsrEngine
from app.pipeline import AsrPipeline
from app.postprocessing.segments import to_segment
from inclusaai_contracts import schema_registry
from inclusaai_contracts.events import AudioChunk


def test_engine_stub_transcribes(settings: Settings) -> None:
    engine = AsrEngine(settings)
    engine.load()  # stub mode (model_name=None)
    out = engine.transcribe(b"0123456789", sample_rate=16000, base_ms=1000)
    assert out and out[0].text


def test_to_segment_is_contract_valid(settings: Settings, audio_chunk: AudioChunk) -> None:
    engine = AsrEngine(settings)
    engine.load()
    pcm = base64.b64decode(audio_chunk.payload_b64)
    transcription = engine.transcribe(
        pcm, sample_rate=audio_chunk.sample_rate, base_ms=audio_chunk.timestamp_ms
    )[0]

    segment = to_segment(audio_chunk, transcription, settings.transcript_language)
    validated = schema_registry.validate("ai.transcript.segment", segment.model_dump())
    assert validated.session_id == "s1"
    assert validated.speaker_id == "spk1"


def test_pipeline_config(settings: Settings) -> None:
    pipeline = AsrPipeline(settings)
    assert pipeline.output_channel is None  # transcripts are foundational, not gated
    assert pipeline.usage_unit == "transcript_segment"
    assert pipeline.engine is not None


async def test_handle_publishes_transcript(
    settings: Settings, audio_chunk: AudioChunk, monkeypatch
) -> None:
    pipeline = AsrPipeline(settings)
    pipeline.engine.load()

    published: list[tuple[str, object]] = []

    async def fake_publish(event_key, payload, *, key=None):  # noqa: ANN001, ANN202
        published.append((event_key, payload))

    monkeypatch.setattr(pipeline, "publish", fake_publish)
    await pipeline.handle("media.audio.chunk", audio_chunk)

    assert published, "expected a transcript to be published"
    assert published[0][0] == "ai.transcript.segment"


async def test_handle_resamples_before_engine(settings: Settings) -> None:
    """A 44.1 kHz chunk is resampled to the target rate by decode_audio, and the
    engine is told that target rate — not the chunk's original one."""
    pipeline = AsrPipeline(settings)
    seen: dict[str, Any] = {}

    class _Recorder:
        def predict(self, payload: dict) -> list[dict]:  # noqa: ANN001
            seen.update(payload)
            return []

    pipeline.engine._model = _Recorder()  # noqa: SLF001 — wiring a fake backend
    pipeline.engine._stub = False  # noqa: SLF001

    chunk = AudioChunk(
        session_id="s1",
        speaker_id="spk1",
        sequence=0,
        timestamp_ms=0,
        encoding="pcm_s16le",
        sample_rate=44100,
        payload_b64=base64.b64encode(b"\x00\x00" * 4410).decode(),
    )
    await pipeline.handle("media.audio.chunk", chunk)

    assert seen["sample_rate"] == 16000
    # 4410 samples at 44.1 kHz -> 1600 samples at 16 kHz (2 bytes each).
    assert len(seen["audio"]) == 1600 * 2
