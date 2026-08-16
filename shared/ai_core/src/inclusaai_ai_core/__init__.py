"""inclusaai_ai_core — the keystone shared library.

Everything a service needs to become a preference-aware, autoscaler-friendly,
usage-metered inference microservice: config, health/readiness, the FastAPI app
factory, and the base Kafka consume→infer→publish pipeline.
"""

from __future__ import annotations

from inclusaai_ai_core.config import BaseServiceSettings
from inclusaai_ai_core.health import Readiness, health_router
from inclusaai_ai_core.pipeline import BaseInferencePipeline
from inclusaai_ai_core.preferences import PreferenceCache
from inclusaai_ai_core.scaling import (
    ACTIVE_SESSIONS,
    QUEUE_DEPTH,
    set_active_sessions,
    set_queue_depth,
)
from inclusaai_ai_core.service import Pipeline, create_app, run

__all__ = [
    "ACTIVE_SESSIONS",
    "QUEUE_DEPTH",
    "BaseInferencePipeline",
    "BaseServiceSettings",
    "Pipeline",
    "PreferenceCache",
    "Readiness",
    "create_app",
    "health_router",
    "run",
    "set_active_sessions",
    "set_queue_depth",
]
