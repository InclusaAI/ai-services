# Convenience wrappers around uv / docker. Requires: uv, docker.
# On Windows without `make`, run the underlying commands (see scripts/) directly.

SERVICES := asr-service sign-recognition-service translation-service tts-service \
            avatar-pose-service vision-quality-service engagement-service

.PHONY: bootstrap sync-shared gen-contracts lint typecheck test dev-up dev-down clean help

help:
	@echo "bootstrap     - uv sync shared workspace + every service"
	@echo "gen-contracts - regenerate gRPC stubs and validate event schemas"
	@echo "lint          - ruff check across the repo"
	@echo "typecheck     - mypy across shared + services"
	@echo "test          - pytest across shared + services"
	@echo "dev-up        - docker compose up local deps (kafka/mlflow/minio/otel)"
	@echo "dev-down      - docker compose down"

bootstrap: sync-shared
	@for s in $(SERVICES); do echo ">> uv sync services/$$s"; (cd services/$$s && uv sync); done

sync-shared:
	uv sync

gen-contracts:
	uv run python scripts/gen_contracts.py

lint:
	uv run ruff check .

typecheck:
	uv run mypy shared services

test:
	uv run pytest

dev-up:
	docker compose -f docker-compose.dev.yml up -d

dev-down:
	docker compose -f docker-compose.dev.yml down

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name '.pytest_cache' -prune -exec rm -rf {} + 2>/dev/null || true
