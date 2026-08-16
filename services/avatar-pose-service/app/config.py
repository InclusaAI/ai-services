"""avatar-pose-service configuration."""

from __future__ import annotations

from inclusaai_ai_core import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "avatar-pose-service"
    kafka_consumer_group: str = "avatar-pose-service"

    # A learned text->pose model is optional; the constrained-vocabulary lookup is
    # the default path (None -> vocabulary only).
    model_name: str | None = None

    # Pose frame rate for the emitted animation.
    fps: int = 30


settings = Settings()
