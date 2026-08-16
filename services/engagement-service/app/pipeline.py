"""engagement pipeline: session participant signals -> periodic ``ai.engagement.signal.aggregate``.

Unlike the other services this one does not publish per input event: it accumulates
session-level signals and flushes an aggregate on a fixed window (like usage
aggregation, and for the same reason — downstream wants windows, not a firehose).
"""

from __future__ import annotations

import asyncio

from pydantic import BaseModel

from inclusaai_ai_core import BaseInferencePipeline
from inclusaai_contracts.events import ParticipantEvent
from inclusaai_kafka_clients.topics import PARTICIPANT_SUBSCRIPTION

from app.aggregation import SessionEngagementAggregator
from app.config import Settings


class EngagementPipeline(BaseInferencePipeline):
    output_channel = None
    usage_unit = "engagement_window"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings, subscription=PARTICIPANT_SUBSCRIPTION)
        self.window_seconds = settings.window_seconds
        self.aggregator = SessionEngagementAggregator()
        self._flush_task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    async def on_start(self) -> None:
        self._stop.clear()
        self._flush_task = asyncio.create_task(self._flush_loop())

    async def on_stop(self) -> None:
        self._stop.set()
        if self._flush_task is not None:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        await self._flush()  # final drain (producer is still up during on_stop)

    async def handle(self, event_key: str, model: BaseModel) -> None:
        if isinstance(model, ParticipantEvent):
            self.aggregator.apply_participant(model)

    async def _flush_loop(self) -> None:
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.window_seconds)
            except asyncio.TimeoutError:
                pass
            await self._flush()

    async def _flush(self) -> None:
        for aggregate in self.aggregator.snapshot_all():
            await self.publish(
                "ai.engagement.signal.aggregate", aggregate, key=aggregate.session_id
            )
