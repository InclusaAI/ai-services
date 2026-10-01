from __future__ import annotations

from app.aggregation import SessionEngagementAggregator
from app.config import Settings
from app.pipeline import EngagementPipeline
from inclusaai_contracts import schema_registry
from inclusaai_contracts.events import EngagementSignalAggregate, ParticipantEvent


def _participant(participant_id: str, event: str, ts: int) -> ParticipantEvent:
    return ParticipantEvent(
        session_id="s1", participant_id=participant_id, event=event, timestamp_ms=ts
    )


def test_aggregator_counts_active_participants() -> None:
    agg = SessionEngagementAggregator()
    agg.apply_participant(_participant("p1", "joined", 1))
    agg.apply_participant(_participant("p2", "joined", 2))
    agg.apply_participant(_participant("p1", "left", 3))
    snapshots = agg.snapshot_all()
    assert len(snapshots) == 1
    assert snapshots[0].participant_count == 1


def test_snapshot_is_contract_valid(joined: ParticipantEvent) -> None:
    agg = SessionEngagementAggregator()
    agg.apply_participant(joined)
    (aggregate,) = agg.snapshot_all()
    validated = schema_registry.validate(
        "ai.engagement.signal.aggregate", aggregate.model_dump()
    )
    assert validated.session_id == "s1"
    assert validated.participant_count == 1


def test_aggregate_carries_no_per_individual_identifier() -> None:
    # PRIVACY (ai-services-IMPLEMENTATION.md §2): the aggregate is session-level only.
    forbidden = {"participant_id", "user_id", "participant_ids", "participants"}
    assert forbidden.isdisjoint(EngagementSignalAggregate.model_fields)


def test_empty_session_is_pruned(joined: ParticipantEvent) -> None:
    agg = SessionEngagementAggregator()
    agg.apply_participant(joined)
    agg.apply_participant(_participant("p1", "left", 5))
    assert agg.snapshot_all() == []


async def test_handle_then_flush_publishes(
    settings: Settings, joined: ParticipantEvent, monkeypatch
) -> None:
    pipeline = EngagementPipeline(settings)
    published: list[tuple[str, object]] = []

    async def fake_publish(event_key, payload, *, key=None):  # noqa: ANN001, ANN202
        published.append((event_key, payload))

    monkeypatch.setattr(pipeline, "publish", fake_publish)
    await pipeline.handle("media.participant", joined)
    await pipeline._flush()
    assert published and published[0][0] == "ai.engagement.signal.aggregate"
    assert isinstance(published[0][1], EngagementSignalAggregate)
