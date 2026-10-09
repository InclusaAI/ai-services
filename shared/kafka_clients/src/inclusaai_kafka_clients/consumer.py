"""Async Kafka consumer wrapper that yields validated, typed event payloads."""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator

from aiokafka import AIOKafkaConsumer
from aiokafka.helpers import create_ssl_context
from inclusaai_contracts import schema_registry
from inclusaai_telemetry import EVENTS_CONSUMED, get_logger
from pydantic import BaseModel

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
        # Build consumer kwargs with optional SASL/SSL support (e.g., for Aiven Kafka)
        consumer_kwargs = {
            "bootstrap_servers": self._bootstrap,
            "group_id": self._group,
            "auto_offset_reset": self._auto_offset_reset,
            "enable_auto_commit": True,
        }

        # Check for SASL/SSL configuration
        security_protocol = os.getenv("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT").upper()
        if security_protocol in ("SASL_SSL", "SASL_PLAINTEXT"):
            consumer_kwargs["security_protocol"] = security_protocol
            consumer_kwargs["sasl_mechanism"] = os.getenv("KAFKA_SASL_MECHANISM", "SCRAM-SHA-256")
            consumer_kwargs["sasl_plain_username"] = os.getenv("KAFKA_SASL_USERNAME", "")
            consumer_kwargs["sasl_plain_password"] = os.getenv("KAFKA_SASL_PASSWORD", "")

            # Load CA certificate if provided (for SSL verification)
            if security_protocol == "SASL_SSL":
                ca_cert = os.getenv("KAFKA_SSL_CA")
                if ca_cert:
                    # Handle escaped newlines in case they get flattened in env vars
                    ca_cert = ca_cert.replace("\\n", "\n")
                    consumer_kwargs["ssl_context"] = create_ssl_context(cadata=ca_cert)

        self._consumer = AIOKafkaConsumer(**consumer_kwargs)
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
