"""asr-service configuration.

Extends the shared BaseServiceSettings with ASR-specific fields. All values are
overridable by environment variables / .env (see repo-root .env.example).
"""

from __future__ import annotations

from inclusaai_ai_core import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "asr-service"
    kafka_consumer_group: str = "asr-service"

    # Registered ASR model, pulled from MLflow by stage/version (ADR-0005).
    # Leave unset (None) to run the deterministic offline stub.
    model_name: str | None = None

    # DEV-ONLY escape hatch: when set (e.g. "base"), load faster-whisper IN-PROCESS
    # and bypass MLflow entirely. Lets ASR run for real on a machine with no model
    # registry. Takes precedence over model_name. Unset in staging/prod.
    asr_whisper_size: str | None = None

    # ASR specifics
    target_sample_rate: int = 16000
    transcript_language: str = "en"

    # Optional gRPC streaming server (implements grpc-contracts AsrService).
    grpc_enabled: bool = False


settings = Settings()
