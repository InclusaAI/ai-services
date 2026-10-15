"""translation-service configuration."""

from __future__ import annotations

from inclusaai_ai_core import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "translation-service"
    kafka_consumer_group: str = "translation-service"

    model_name: str | None = "translation-nllb"
    # DEV-ONLY (translation-service): set to a real HF MT model id (e.g.
    # Helsinki-NLP/opus-mt-en-es, whose id fixes the language pair) to load it
    # IN-PROCESS and bypass MLflow entirely — real translation on a box with no
    # registry. Requires the runtime extras: uv sync --extra real-model.
    # Takes precedence over MODEL_NAME; leave unset in staging/prod.
    translation_model_id: str | None = None

    default_source_language: str = "en"
    # TODO(prefs): fan out one translation per distinct participant target language
    # (AccessibilityPreferenceUpdated.translation_target_language). The scaffold uses
    # a single default target.
    default_target_language: str = "es"


settings = Settings()
