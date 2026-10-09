# InclusaAI sign-recognition-service image.
#
# Build from the REPO ROOT so the shared/ path-dependencies are in context:
#   docker build -f services/sign-recognition-service/Dockerfile -t inclusaai/sign-recognition-service .
#
# BASE_IMAGE defaults to a slim CPU image so the scaffold builds anywhere; pass the
# GPU base (docker/python-cuda-base.Dockerfile) in the cluster:
#   --build-arg BASE_IMAGE=ghcr.io/inclusaai/python-cuda-base:3.11
ARG BASE_IMAGE=python:3.11-slim
FROM ${BASE_IMAGE}

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

ENV PYTHONUNBUFFERED=1     UV_LINK_MODE=copy     UV_COMPILE_BYTECODE=1

WORKDIR /workspace
COPY shared/ /workspace/shared/
COPY services/sign-recognition-service/ /workspace/services/sign-recognition-service/

WORKDIR /workspace/services/sign-recognition-service
RUN uv sync --no-dev

EXPOSE 8080 50051
CMD ["sh", "-c", "exec uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
