#!/usr/bin/env bash
# Bring up local dev dependencies (redpanda/Kafka, MLflow, MinIO, OTel collector).
# The non-`make` entrypoint for `make dev-up` (see Makefile). Requires: docker.
set -euo pipefail

cd "$(dirname "$0")/.."   # repo root

docker compose -f docker-compose.dev.yml up -d "$@"

cat <<'EOF'

local dev stack is starting. Endpoints (see .env.example):
  Kafka (redpanda)     localhost:9092
  MLflow UI            http://localhost:5000
  MinIO console        http://localhost:9001   (minioadmin / minioadmin)
  MinIO S3 API         http://localhost:9000
  OTel collector OTLP  localhost:4317

Tear down with:  docker compose -f docker-compose.dev.yml down   (or `make dev-down`)
EOF
