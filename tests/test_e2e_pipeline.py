"""End-to-end pipeline test over the local dev stack (gated).

Flow: publish a ``media.session.<id>.audio.chunk`` to the local broker -> the
running asr-service transcribes it (stub engine when no model is registered) ->
assert an ``ai.transcript.segment`` for that session appears.

Prerequisites (run once):

    make dev-up                 # redpanda on localhost:9092 (+ mlflow/minio/otel)
    cd services/asr-service && uv run uvicorn app.main:app --port 8080

Run from the repo ROOT env (the shared workspace has the kafka_clients):

    RUN_E2E_TESTS=1 uv run pytest tests/test_e2e_pipeline.py -v

Skipped by default: it needs a live broker + a running service, so it is not part
of CI — exactly the cross-service tests the repo's ``tests/README.md`` reserves
this directory for.
"""

from __future__ import annotations

import asyncio
import base64
import os
import socket
import time

import httpx
import pytest
from inclusaai_contracts.events import AudioChunk
from inclusaai_kafka_clients import KafkaEventConsumer, KafkaEventProducer
from inclusaai_kafka_clients.topics import audio_chunk_topic

_BROKER = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
_SERVICE_URL = os.environ.get("ASR_SERVICE_URL", "http://localhost:8080")


def _broker_reachable(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _parse_broker(addr: str) -> tuple[str, int]:
    host, _, port = addr.rpartition(":")
    return host or "localhost", int(port)


@pytest.mark.skipif(
    os.environ.get("RUN_E2E_TESTS") != "1",
    reason="set RUN_E2E_TESTS=1 to run against the local dev stack (make dev-up)",
)
@pytest.mark.asyncio
async def test_asr_chunk_to_transcript_end_to_end() -> None:
    # --- prerequisites ---
    host, port = _parse_broker(_BROKER)
    if not _broker_reachable(host, port):
        pytest.skip(f"kafka broker not reachable at {_BROKER} (run `make dev-up` first)")
    try:
        health = httpx.get(f"{_SERVICE_URL}/healthz", timeout=3)
    except httpx.ConnectError:
        pytest.skip(f"asr-service not running at {_SERVICE_URL}")
    assert health.status_code == 200

    # --- publish one audio chunk on a unique per-session topic ---
    session_id = f"e2e-{int(time.time() * 1000)}"
    # 16 kHz mono pcm_s16le; 10 bytes is enough for the stub engine (it keys off length).
    chunk = AudioChunk(
        session_id=session_id,
        speaker_id="e2e-speaker",
        sequence=0,
        timestamp_ms=0,
        sample_rate=16000,
        encoding="pcm_s16le",
        payload_b64=base64.b64encode(b"0123456789").decode(),
    )
    producer = KafkaEventProducer(_BROKER, "e2e-test")
    consumer = KafkaEventConsumer(
        _BROKER,
        group_id=f"e2e-verify-{session_id}",
        topics=["ai.transcript.segment"],
        auto_offset_reset="earliest",
        service_name="e2e-test",
    )
    await producer.start()
    await consumer.start()
    try:
        await producer.publish(
            "media.audio.chunk", chunk, topic=audio_chunk_topic(session_id), key=session_id
        )

        # --- wait for the service to publish a transcript for our session ---
        deadline = asyncio.get_running_loop().time() + 30.0
        async for event_key, model, _record in consumer.messages():
            assert event_key == "ai.transcript.segment"
            if model.session_id == session_id:
                assert model.text  # stub or real transcript is never empty
                return
            if asyncio.get_running_loop().time() > deadline:
                break
        pytest.fail(f"no ai.transcript.segment for session {session_id} within 30s")
    finally:
        await consumer.stop()
        await producer.stop()
