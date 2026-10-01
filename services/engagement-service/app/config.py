"""engagement-service configuration."""

from __future__ import annotations

from inclusaai_ai_core import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "engagement-service"
    kafka_consumer_group: str = "engagement-service"

    # No ML model — pure aggregation.
    model_name: str | None = None

    # How often to publish a session-level engagement aggregate.
    window_seconds: int = 60


settings = Settings()
