"""vision-quality-service configuration."""

from __future__ import annotations

from inclusaai_ai_core import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "vision-quality-service"
    kafka_consumer_group: str = "vision-quality-service"

    # Quality checks are heuristic by default; a learned model is optional.
    model_name: str | None = None

    video_sample_fps: int = 15  # ADR-0007 starting point


settings = Settings()
