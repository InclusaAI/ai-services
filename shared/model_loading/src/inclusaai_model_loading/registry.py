"""Pull validated, versioned models from the shared MLflow registry.

This repo consumes **only registered, versioned models** — never a raw checkpoint
from a research notebook (ai-services-IMPLEMENTATION.md §3, ADR-0005). The MLflow
instance itself is owned/hosted by inclusaai-infra; this client only reads.
"""

from __future__ import annotations

import os
from typing import Any

from inclusaai_telemetry import get_logger

log = get_logger(__name__)


class ModelNotAvailable(RuntimeError):
    """Raised when a requested registered model/version can't be loaded.

    In production this should fail readiness — never silently fall back to an
    unregistered artifact."""


def resolve_model_uri(name: str, stage: str | None = None, version: str | None = None) -> str:
    """Build an MLflow ``models:/`` URI. Prefer an explicit version; else a stage."""
    if version:
        return f"models:/{name}/{version}"
    return f"models:/{name}/{stage or 'Production'}"


def load_model(
    name: str,
    *,
    stage: str | None = None,
    version: str | None = None,
    tracking_uri: str | None = None,
) -> Any:
    """Load a registered model as an ``mlflow.pyfunc`` model.

    Raises ``ModelNotAvailable`` if the registry has no matching version.
    """
    import mlflow

    # Fail fast when the registry is unreachable (e.g. running offline with no MLflow):
    # cap MLflow's HTTP retries/timeout so an absent registry falls through to the
    # caller's stub in seconds instead of a minutes-long retry-backoff storm that would
    # block service startup. setdefault -> inclusaai-infra can raise these in
    # staging/prod, where a transient registry blip is worth retrying.
    os.environ.setdefault("MLFLOW_HTTP_REQUEST_MAX_RETRIES", "1")
    os.environ.setdefault("MLFLOW_HTTP_REQUEST_TIMEOUT", "5")

    if tracking_uri:
        mlflow.set_tracking_uri(tracking_uri)

    uri = resolve_model_uri(name, stage=stage, version=version)
    log.info("model.loading", uri=uri, tracking_uri=tracking_uri or mlflow.get_tracking_uri())
    try:
        model = mlflow.pyfunc.load_model(uri)
    except Exception as exc:  # noqa: BLE001 — normalise any backend error to our type
        raise ModelNotAvailable(
            f"Could not load {uri!r} from MLflow. Has research promoted/registered it "
            f"through the evaluation gate (see ADR-0005)?"
        ) from exc
    log.info("model.loaded", uri=uri)
    return model
