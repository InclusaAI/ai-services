"""Common configuration for every inference service, from environment variables.

Service-specific settings subclass ``BaseServiceSettings`` and add their own fields
(model name/version, topic subscriptions, sampling rates, etc.).
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseServiceSettings(BaseSettings):
    # protected_namespaces=() so `model_*` fields don't collide with pydantic internals.
    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", protected_namespaces=()
    )

    # identity
    service_name: str = "ai-service"
    env: str = "dev"
    log_level: str = "INFO"

    # bind
    http_host: str = "0.0.0.0"
    http_port: int = 8080
    grpc_port: int = 50051

    # kafka
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_consumer_group: str = "ai-service"

    # mlflow model registry (read-only; hosted by inclusaai-infra per ADR-0005)
    mlflow_tracking_uri: str = "http://localhost:5000"
    model_name: str | None = None
    model_stage: str = "Production"
    model_version: str | None = None

    # observability
    otel_exporter_otlp_endpoint: str | None = None

    # usage aggregation (ADR-0009)
    usage_aggregate_interval_seconds: int = 60

    # production honesty gates (see ai_core/pipeline.py::readiness_problems).
    # REQUIRE_KAFKA: the broker must be reachable and the consume loop running,
    # or /readyz returns 503 (offline-stub stays a dev-only luxury).
    # REQUIRE_MODEL: when a real model is configured via MODEL_NAME, it must have
    # actually loaded; falling back to the stub flips readiness off. Leave
    # REQUIRE_MODEL unset for services whose default path is the stub (asr in
    # dev, avatar-pose vocabulary mode, vision-quality heuristics).
    require_kafka: bool = False
    require_model: bool = False
