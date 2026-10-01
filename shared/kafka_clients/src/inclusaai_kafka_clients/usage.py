"""Periodic ``ai.usage.aggregate`` publishing (ADR-0009).

Billing needs periodic counts, not one Kafka event per inference. Each service
records units as it works; this aggregator flushes accumulated counts on an
interval as ``ai.usage.aggregate`` events.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict

from inclusaai_contracts.events import UsageAggregate
from inclusaai_telemetry import get_logger
from inclusaai_utils import now_ms

from inclusaai_kafka_clients.producer import KafkaEventProducer

log = get_logger(__name__)


class UsageAggregator:
    """Accumulate usage counts per unit and flush them periodically."""

    def __init__(
        self,
        producer: KafkaEventProducer,
        service_name: str,
        interval_seconds: int = 60,
    ) -> None:
        self._producer = producer
        self._service = service_name
        self._interval = interval_seconds
        self._counts: dict[str, int] = defaultdict(int)
        self._window_start = now_ms()
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    def record(self, unit: str, n: int = 1) -> None:
        self._counts[unit] += n

    async def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self._interval)
            except TimeoutError:
                pass
            await self.flush()

    async def flush(self) -> None:
        if not self._counts:
            self._window_start = now_ms()
            return
        window_end = now_ms()
        snapshot = dict(self._counts)
        self._counts.clear()
        for unit, count in snapshot.items():
            await self._producer.publish(
                "ai.usage.aggregate",
                UsageAggregate(
                    service_name=self._service,
                    window_start_ms=self._window_start,
                    window_end_ms=window_end,
                    unit=unit,
                    count=count,
                ),
            )
        self._window_start = window_end

    def start(self) -> None:
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            await self._task
        await self.flush()  # final drain
