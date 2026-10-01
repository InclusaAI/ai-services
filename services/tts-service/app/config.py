"""tts-service configuration."""

from __future__ import annotations

from inclusaai_ai_core import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "tts-service"
    kafka_consumer_group: str = "tts-service"

    model_name: str | None = "tts-vits"

    sample_rate: int = 24000
    encoding: str = "pcm_s16le"


settings = Settings()
