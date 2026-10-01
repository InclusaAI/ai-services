"""sign-recognition-service configuration."""

from __future__ import annotations

from inclusaai_ai_core import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "sign-recognition-service"
    kafka_consumer_group: str = "sign-recognition-service"

    # Registered recognition model (None -> offline stub).
    model_name: str | None = "sign-recognition-asl"

    # Video sampling rate the upstream media backend emits at (ADR-0007 starting point).
    video_sample_fps: int = 15
    # ASL only for MVP; the recognized vocabulary is the SAME closed set the avatar
    # generates from (symmetric vocabulary, ADR-0002).
    sign_language: str = "ASL"


settings = Settings()
