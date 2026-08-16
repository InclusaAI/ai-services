# models/

**Nothing here is committed.** Model weights are pulled at runtime from the MLflow
model registry — never checked into git, never loaded from a raw checkpoint path
([ADR-0005](../files/ADR-0005-model-registry-ownership.md), IMPLEMENTATION §3).

`.gitignore` keeps everything in this directory out of the repo except this README:

```
models/*
!models/README.md
*.pt  *.pth  *.onnx  *.ckpt  mlruns/
```

## How a service gets its model

Each service's `config.py` names a **registered model** and a stage or explicit
version — e.g. `MODEL_NAME=asr-whisper`, `MODEL_STAGE=Production`. On startup the
service calls `inclusaai_model_loading.load_model(name, stage=…, version=…)` against
`MLFLOW_TRACKING_URI`.

If the registry has no such model (local dev, CI, this scaffold), `load_model` raises
`ModelNotAvailable` and the engine falls back to a **deterministic offline stub**, so
the service still boots, serves health endpoints, and passes tests. This directory is
therefore only populated when MLflow materializes artifacts locally.

## Local registry

`make dev-up` starts a local MLflow (`http://localhost:5000`) backed by postgres +
MinIO. Register a model there to exercise the real load path; see
[docker-compose.dev.yml](../docker-compose.dev.yml).

> The promotion gate (accuracy / latency / fairness thresholds a model must clear to
> reach `Production`) is owned by `inclusaai-docs` and is **not yet in this repo** —
> see the root README "Missing docs".
