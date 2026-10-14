"""Reusable inference pipeline: consume → preference-gate → infer → publish.

This is the reference plumbing every service reuses so each service body stays
small. It wires in, once, all the cross-cutting requirements from the docs/ADRs:

  * preference-aware gating         (IMPLEMENTATION §5/§9)  -> should_generate()
  * scaling signals for autoscaler  (ADR-0008)              -> active_sessions gauge
  * periodic usage aggregation      (ADR-0009)              -> UsageAggregator
  * graceful startup/shutdown       (quality bar §8)        -> start()/stop()

A concrete service subclasses this, sets ``output_channel`` / ``usage_unit``,
implements ``on_start`` (load model) and ``handle`` (run inference + publish).
"""

from __future__ import annotations

import asyncio
from typing import Any

from inclusaai_contracts.events import AccessibilityChannel, AccessibilityPreferenceUpdated
from inclusaai_kafka_clients import KafkaEventConsumer, KafkaEventProducer, UsageAggregator
from inclusaai_telemetry import INFERENCE_ERRORS, get_logger
from pydantic import BaseModel

from inclusaai_ai_core.config import BaseServiceSettings
from inclusaai_ai_core.preferences import PreferenceCache
from inclusaai_ai_core.scaling import set_active_sessions

log = get_logger(__name__)


class BaseInferencePipeline:
    """Base class for a service's Kafka consume/infer/publish loop."""

    #: The accessibility channel this service's output serves; None = always generate.
    output_channel: AccessibilityChannel | None = None
    #: The usage unit counted for ai.usage.aggregate (ADR-0009).
    usage_unit: str = "inference"
    #: True once the service's real model (if one is required) has loaded. Services
    #: set False in ``on_start`` when a configured model failed to load; leave True
    #: for stub/vocabulary paths. ``readiness_problems`` turns this into /readyz.
    model_ready: bool = True

    def __init__(
        self,
        settings: BaseServiceSettings,
        *,
        subscription: str | None = None,
        topics: list[str] | None = None,
    ) -> None:
        if not subscription and not topics:
            raise ValueError("pipeline needs a `subscription` pattern or a `topics` list")
        self.settings = settings
        self._subscription = subscription
        self._topics = topics
        self.producer = KafkaEventProducer(settings.kafka_bootstrap_servers, settings.service_name)
        self.preferences = PreferenceCache()
        self.usage = UsageAggregator(
            self.producer, settings.service_name, settings.usage_aggregate_interval_seconds
        )
        self._input_consumer: KafkaEventConsumer | None = None
        self._pref_consumer: KafkaEventConsumer | None = None
        self._tasks: list[asyncio.Task[Any]] = []

    # ------------------------------------------------------------------ lifecycle
    async def start(self) -> None:
        await self.producer.start()
        await self.on_start()
        self.usage.start()

        # OFFLINE: the broker is absent/unreachable (producer stayed offline), so there
        # is nothing to consume and nowhere to publish. Boot the HTTP surface + stub
        # inference only, and skip the consume loops. Lets the whole platform run with
        # no Kafka (README Quickstart); production readiness should gate on this.
        if not self.producer.online:
            log.warning(
                "pipeline.offline",
                service=self.settings.service_name,
                reason="kafka broker unavailable; consume/publish loop disabled",
            )
            return

        # NOTE: in a multi-replica deployment each replica needs to see ALL preference
        # updates, so this group should be made replica-unique in production.
        self._pref_consumer = KafkaEventConsumer(
            self.settings.kafka_bootstrap_servers,
            f"{self.settings.service_name}-prefs",
            topics=["accessibility.preference.updated"],
            service_name=self.settings.service_name,
        )
        await self._pref_consumer.start()
        self._tasks.append(asyncio.create_task(self._run_preferences()))

        self._input_consumer = KafkaEventConsumer(
            self.settings.kafka_bootstrap_servers,
            self.settings.kafka_consumer_group,
            topics=self._topics,
            pattern=self._subscription,
            service_name=self.settings.service_name,
        )
        await self._input_consumer.start()
        self._tasks.append(asyncio.create_task(self._run_input()))
        log.info("pipeline.started", service=self.settings.service_name)

    async def stop(self) -> None:
        for consumer in (self._input_consumer, self._pref_consumer):
            if consumer is not None:
                await consumer.stop()
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            try:
                await task
            except (asyncio.CancelledError, GeneratorExit):
                pass
            except Exception as exc:  # noqa: BLE001 — a crashed loop must not abort the other shutdown steps
                log.error("pipeline.stop_task_failed", error=str(exc))
        self._tasks.clear()
        await self.usage.stop()
        await self.on_stop()
        await self.producer.stop()
        log.info("pipeline.stopped", service=self.settings.service_name)

    # --------------------------------------------------------------------- loops
    async def _run_preferences(self) -> None:
        assert self._pref_consumer is not None
        async for _key, model, _record in self._pref_consumer.messages():
            if isinstance(model, AccessibilityPreferenceUpdated):
                self.preferences.update(model)
                set_active_sessions(self.settings.service_name, self.preferences.session_count())

    async def _run_input(self) -> None:
        assert self._input_consumer is not None
        async for event_key, model, _record in self._input_consumer.messages():
            try:
                await self.handle(event_key, model)
            except Exception as exc:  # noqa: BLE001 — a bad message must not kill the loop
                INFERENCE_ERRORS.labels(self.settings.service_name).inc()
                log.error("pipeline.handle_failed", event_key=event_key, error=str(exc))

    # ---------------------------------------------------------- helpers for subclasses
    def should_generate(self, session_id: str) -> bool:
        """Preference gate: whether to spend GPU producing this service's output."""
        if self.output_channel is None:
            return True
        return self.preferences.should_generate(session_id, self.output_channel)

    def readiness_problems(self) -> list[str]:
        """Return readiness problems per the REQUIRE_* honesty gates.

        Empty list = this instance is actually doing (or able to do) its job.
        Non-empty = /readyz must be 503: Render (or K8s) stops routing and the
        offline-stub luxury doesn't masquerade as a serving deployment.
        """
        problems: list[str] = []
        if self.settings.require_kafka and not (
            self.producer.online and self._input_consumer is not None
        ):
            problems.append("kafka-broker-unreachable")
        if self.settings.require_model and not self.model_ready:
            problems.append("model-not-loaded")
        return problems

    async def publish(self, event_key: str, payload: BaseModel, *, key: str | None = None) -> None:
        await self.producer.publish(event_key, payload, key=key)
        self.usage.record(self.usage_unit)

    # ----------------------------------------------------------------- override me
    async def on_start(self) -> None:
        """Load the model / warm caches. Default: no-op."""

    async def on_stop(self) -> None:
        """Release resources. Default: no-op."""

    async def handle(self, event_key: str, model: BaseModel) -> None:
        """Run inference on one input event and publish the result(s)."""
        raise NotImplementedError
