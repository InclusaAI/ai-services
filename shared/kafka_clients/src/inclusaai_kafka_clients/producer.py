"""Async Kafka producer wrapper that speaks typed event payloads."""

from __future__ import annotations

import json
from typing import Any

from aiokafka import AIOKafkaProducer
from pydantic import BaseModel

from inclusaai_kafka_clients.topics import topic_for_event_key
from inclusaai_telemetry import EVENTS_PUBLISHED, get_logger

log = get_logger(__name__)


class KafkaEventProducer:
    """Publishes pydantic event models as JSON to their topic.

    Usage:
        producer = KafkaEventProducer(bootstrap, service_name)
        await producer.start()
        await producer.publish("ai.transcript.segment", segment)
        await producer.stop()
    """

    def __init__(self, bootstrap_servers: str, service_name: str = "ai-service") -> None:
        self._bootstrap = bootstrap_servers
        self._service = service_name
        self._producer: AIOKafkaProducer | None = None
        #: True once connected to a broker; stays False in offline mode (no broker
        #: configured or unreachable), which callers use to skip the consume loop.
        self.online = False

    async def start(self) -> None:
        # OFFLINE MODE: with no broker configured, or one that can't be reached, the
        # service still boots and serves its HTTP surface + stub inference — no events
        # flow. This mirrors the model path (engine falls back to a stub when MLflow
        # is absent) so the whole platform is runnable with no infra. Logged loudly;
        # production readiness should treat an unreachable broker as a hard failure.
        if not self._bootstrap.strip():
            log.warning(
                "producer.offline", service=self._service, reason="no kafka broker configured"
            )
            return
        producer = AIOKafkaProducer(bootstrap_servers=self._bootstrap)
        try:
            await producer.start()
        except Exception as exc:  # noqa: BLE001 — broker unreachable must not block boot
            log.warning(
                "producer.offline",
                service=self._service,
                bootstrap=self._bootstrap,
                error=str(exc),
            )
            await producer.stop()  # release the half-opened client (no 'Unclosed AIOKafkaProducer')
            return
        self._producer = producer
        self.online = True
        log.info("producer.started", bootstrap=self._bootstrap)

    async def stop(self) -> None:
        if self._producer is not None:
            await self._producer.stop()
            self._producer = None
            log.info("producer.stopped")

    async def publish(
        self,
        event_key: str,
        payload: BaseModel | dict[str, Any],
        *,
        topic: str | None = None,
        key: str | None = None,
    ) -> None:
        if self._producer is None:
            # Offline mode (no reachable broker): drop the event. The service is
            # running for its HTTP surface only; there is nowhere to publish.
            return
        dest = topic or topic_for_event_key(event_key)
        raw = (
            payload.model_dump_json().encode()
            if isinstance(payload, BaseModel)
            else json.dumps(payload).encode()
        )
        await self._producer.send_and_wait(
            dest, value=raw, key=key.encode() if key else None
        )
        EVENTS_PUBLISHED.labels(self._service, event_key).inc()
