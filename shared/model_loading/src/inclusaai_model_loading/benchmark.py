"""Latency/accuracy benchmarking (quality bar §8): mirror latency to Prometheus
and optionally persist benchmark runs to MLflow."""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from inclusaai_telemetry import INFERENCE_LATENCY, get_logger

log = get_logger(__name__)


@contextmanager
def measure_latency(service: str, model: str) -> Iterator[None]:
    """Time a block of inference and record it to the ``inference_latency_seconds``
    histogram (labelled by service + model)."""
    start = time.perf_counter()
    try:
        yield
    finally:
        INFERENCE_LATENCY.labels(service, model).observe(time.perf_counter() - start)


def log_benchmark_to_mlflow(
    run_name: str,
    metrics: dict[str, float],
    *,
    params: dict[str, Any] | None = None,
    experiment: str = "ai-services-benchmarks",
    tracking_uri: str | None = None,
) -> None:
    """Persist a benchmark (latency/accuracy/fairness metrics) as an MLflow run so a
    regression in a promoted model is traceable to a specific run."""
    import mlflow

    if tracking_uri:
        mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(experiment)
    with mlflow.start_run(run_name=run_name):
        if params:
            mlflow.log_params(params)
        mlflow.log_metrics(metrics)
    log.info("benchmark.logged", run_name=run_name, metrics=metrics)
