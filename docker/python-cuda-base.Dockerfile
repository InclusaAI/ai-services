# InclusaAI GPU base image for inference services.
#
# Aligns with inclusaai-infra `base-images/python-cuda-base` (that repo's CONTRACT.md
# is not yet in this tree — see the root README "Missing docs"; this is the
# ai-services-side placeholder, kept deliberately minimal).
#
# Heavy services (asr, sign-recognition, translation, tts, vision-quality) build
# against this instead of the default slim base by passing:
#     --build-arg BASE_IMAGE=ghcr.io/inclusaai/python-cuda-base:3.11
# to their own `docker build`. CPU-only services (avatar-pose in vocab mode,
# engagement) keep the default python:3.11-slim.
#
# Build (from the repo root):
#   docker build -f docker/python-cuda-base.Dockerfile \
#     -t ghcr.io/inclusaai/python-cuda-base:3.11 .
ARG CUDA_VERSION=12.4.1
ARG CUDNN=cudnn
ARG UBUNTU=ubuntu22.04
FROM nvidia/cuda:${CUDA_VERSION}-${CUDNN}-runtime-${UBUNTU}

ARG PYTHON_VERSION=3.11
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

# Python + the shared libs opencv/mediapipe need (libGL, glib).
RUN apt-get update && apt-get install -y --no-install-recommends \
        software-properties-common ca-certificates curl \
    && add-apt-repository -y ppa:deadsnakes/ppa \
    && apt-get update && apt-get install -y --no-install-recommends \
        "python${PYTHON_VERSION}" "python${PYTHON_VERSION}-venv" "python${PYTHON_VERSION}-dev" \
        libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf "/usr/bin/python${PYTHON_VERSION}" /usr/bin/python3 \
    && ln -sf "/usr/bin/python${PYTHON_VERSION}" /usr/bin/python

# Same uv the services use, so `uv sync` in a downstream Dockerfile behaves identically.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/
