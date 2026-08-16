"""MLflow model-registry access (read-only) + benchmarking."""

from inclusaai_model_loading.benchmark import log_benchmark_to_mlflow, measure_latency
from inclusaai_model_loading.registry import ModelNotAvailable, load_model, resolve_model_uri

__all__ = [
    "load_model",
    "resolve_model_uri",
    "ModelNotAvailable",
    "measure_latency",
    "log_benchmark_to_mlflow",
]
