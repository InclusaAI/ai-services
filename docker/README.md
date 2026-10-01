# docker/

Shared image-build assets for ai-services. Not application code.

| File | Purpose |
|---|---|
| `python-cuda-base.Dockerfile` | GPU base image (CUDA + cuDNN runtime + Python 3.11 + uv) that GPU-bound services extend via `--build-arg BASE_IMAGE=…`. Mirrors `inclusaai-infra`'s `base-images/python-cuda-base`. |
| `otel-collector.yaml` | OpenTelemetry Collector config used by `docker-compose.dev.yml`. |

## Base-image strategy

Each service's own `Dockerfile` takes a `BASE_IMAGE` build arg that defaults to
`python:3.11-slim` so the scaffold builds anywhere with no GPU. In the cluster, the
GPU-bound services are built against the CUDA base:

```bash
# 1. build the base once (from the repo root)
docker build -f docker/python-cuda-base.Dockerfile \
  -t ghcr.io/inclusaai/python-cuda-base:3.11 .

# 2. build a service against it (still from the repo root — services need the
#    shared/ path-deps in the build context)
docker build -f services/asr-service/Dockerfile \
  --build-arg BASE_IMAGE=ghcr.io/inclusaai/python-cuda-base:3.11 \
  -t inclusaai/asr-service .
```

| Service | Base in prod |
|---|---|
| asr, sign-recognition, translation, tts, vision-quality | CUDA base (GPU) |
| avatar-pose (vocab mode), engagement | slim (CPU) |

> **Placeholder note.** The authoritative base image, required labels/annotations,
> and tag conventions belong to `inclusaai-infra` (`CONTRACT.md`), which is not in
> this repo yet. Reconcile this Dockerfile with it when it lands; keep the image
> name (`ghcr.io/inclusaai/python-cuda-base`) stable so service Dockerfiles don't
> need to change.
