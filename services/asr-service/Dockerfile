# InclusaAI asr-service image.
#
# Build from the REPO ROOT so the shared/ path-dependencies are in the build
# context and the ../../shared relative layout is preserved:
#
#   docker build -f services/asr-service/Dockerfile -t inclusaai/asr-service .
#
# BASE_IMAGE defaults to a slim CPU image so the scaffold builds anywhere. In the
# cluster, pass the GPU base built from docker/python-cuda-base.Dockerfile
# (aligned with inclusaai-infra base-images), e.g.
#   --build-arg BASE_IMAGE=ghcr.io/inclusaai/python-cuda-base:3.11
ARG BASE_IMAGE=python:3.11-slim
FROM ${BASE_IMAGE}

# uv for fast, reproducible installs.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

ENV PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

WORKDIR /workspace
# Preserve the monorepo layout so ../../shared path-deps resolve.
COPY shared/ /workspace/shared/
COPY services/asr-service/ /workspace/services/asr-service/

WORKDIR /workspace/services/asr-service
RUN uv sync --no-dev

EXPOSE 8080 50051
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
    CMD ["uv", "run", "python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8080/healthz').status==200 else 1)"]

CMD ["sh", "-c", "exec uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
