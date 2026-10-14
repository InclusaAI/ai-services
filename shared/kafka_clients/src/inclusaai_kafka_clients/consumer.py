"""Async Kafka consumer wrapper that yields validated, typed event payloads."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from aiokafka import AIOKafkaConsumer
from inclusaai_contracts import schema_registry
from inclusaai_telemetry import EVENTS_CONSUMED, get_logger
from pydantic import BaseModel

from inclusaai_kafka_clients.security import security_kwargs
from inclusaai_kafka_clients.topics import topic_to_event_key

log = get_logger(__name__)


class KafkaEventConsumer:
    """Consumes a topic list and/or a regex pattern, decoding each message into its
    pydantic model via the contracts schema registry.

    Usage:
        consumer = KafkaEventConsumer(bootstrap, group, pattern=AUDIO_CHUNK_SUBSCRIPTION)
        await consumer.start()
        async for event_key, model, record in consumer.messages():
            ...
        await consumer.stop()   # ends the async-for cleanly (graceful shutdown)
    """

    def __init__(
        self,
        bootstrap_servers: str,
        group_id: str,
        *,
        topics: list[str] | None = None,
        pattern: str | None = None,
        service_name: str = "ai-service",
        auto_offset_reset: str = "latest",
    ) -> None:
        if not topics and not pattern:
            raise ValueError("KafkaEventConsumer needs either `topics` or `pattern`.")
        self._bootstrap = bootstrap_servers
        self._group = group_id
        self._topics = topics
        self._pattern = pattern
        self._service = service_name
        self._auto_offset_reset = auto_offset_reset
        self._consumer: AIOKafkaConsumer | None = None

    async def start(self) -> None:
        self._consumer = AIOKafkaConsumer(
            bootstrap_servers=self._bootstrap,
            group_id=self._group,
            auto_offset_reset=self._auto_offset_reset,
            enable_auto_commit=True,
            **security_kwargs(),
        )
        if self._pattern:
            self._consumer.subscribe(pattern=self._pattern)
        else:
            self._consumer.subscribe(topics=self._topics)
        await self._consumer.start()
        log.info("consumer.started", group=self._group, topics=self._topics, pattern=self._pattern)

    async def stop(self) -> None:
        if self._consumer is not None:
            await self._consumer.stop()
            self._consumer = None
            log.info("consumer.stopped")

    async def messages(self) -> AsyncIterator[tuple[str, BaseModel, object]]:
        if self._consumer is None:
            raise RuntimeError("KafkaEventConsumer.start() must be called before messages().")
        async for record in self._consumer:
            try:
                event_key = topic_to_event_key(record.topic)
                model = schema_registry.validate(event_key, json.loads(record.value.decode()))
            except Exception as exc:  # noqa: BLE001 — a poison message must not kill the loop
                log.warning("consumer.decode_failed", topic=record.topic, error=str(exc))
                continue
            EVENTS_CONSUMED.labels(self._service, event_key).inc()
            yield event_key, model, record
