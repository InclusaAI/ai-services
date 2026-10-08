#!/usr/bin/env bash
# Sync the shared-library workspace and every standalone service project.
# The non-`make` entrypoint for `make bootstrap` (see Makefile); handy on Windows
# via Git Bash / WSL. Requires: uv.
set -euo pipefail

cd "$(dirname "$0")/.."   # repo root

SERVICES=(
  asr-service
  sign-recognition-service
  translation-service
  tts-service
  avatar-pose-service
  vision-quality-service
  engagement-service
)

# --all-packages installs the shared workspace members into the root env so
# root-level `pytest` (shared/*/tests + tests/) and the E2E tests can import
# inclusaai_* directly.
echo ">> uv sync (shared workspace + repo tooling)"
uv sync --all-packages

echo ">> generating contract stubs + schemas"
uv run python scripts/gen_contracts.py

for svc in "${SERVICES[@]}"; do
  echo ">> uv sync services/$svc"
  ( cd "services/$svc" && uv sync )
done

echo "bootstrap complete."
