from __future__ import annotations

import pytest
from app.config import Settings
from inclusaai_contracts.events import ParticipantEvent


@pytest.fixture
def settings() -> Settings:
    return Settings(
        service_name="engagement-test",
        otel_exporter_otlp_endpoint=None,
        window_seconds=60,
    )


@pytest.fixture
def joined() -> ParticipantEvent:
    return ParticipantEvent(
        session_id="s1",
        participant_id="p1",
        event="joined",
        timestamp_ms=1000,
    )
