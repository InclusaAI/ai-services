"""Thin wrapper over the shared model_loading library.

Keeps the MLflow pull in one place so the engine doesn't reach into shared
internals directly. Models are pulled by registered stage/version only — never a
raw checkpoint (ADR-0005).
"""

from __future__ import annotations

from typing import Any

from inclusaai_model_loading import load_model

from app.config import Settings


def load_asr_model(settings: Settings) -> Any:
    """Load the registered ASR model referenced by ``settings``.

    Raises ``inclusaai_model_loading.ModelNotAvailable`` if the registry has no
    matching version (caller decides whether to fail readiness or stub).
    """
    assert settings.model_name is not None  # guarded by the engine before calling
    return load_model(
        settings.model_name,
        stage=settings.model_stage,
        version=settings.model_version,
        tracking_uri=settings.mlflow_tracking_uri,
    )
