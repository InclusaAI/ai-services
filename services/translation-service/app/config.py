"""translation-service configuration."""

from __future__ import annotations

from inclusaai_ai_core import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "translation-service"
    kafka_consumer_group: str = "translation-service"

    model_name: str | None = "translation-nllb"

    default_source_language: str = "en"
    # TODO(prefs): fan out one translation per distinct participant target language
    # (AccessibilityPreferenceUpdated.translation_target_language). The scaffold uses
    # a single default target.
    default_target_language: str = "es"


settings = Settings()
