# tests/

Home for **cross-service / integration** tests — flows that span more than one
service and therefore don't belong to any single `services/<svc>/tests/` suite.

Per-service unit tests live with their service (`services/<svc>/tests/`) and run in
that service's own `uv` environment (`cd services/<svc> && uv run pytest`). This
directory is for things like:

- an end-to-end pipeline over a local redpanda: publish `media.*.audio.chunk` →
  assert an `ai.transcript.segment` appears, then `ai.translation.result`, etc.;
- contract round-trips: every `EVENT_MODELS` payload validates against its generated
  JSON Schema (see [scripts/gen_contracts.py](../scripts/gen_contracts.py));
- preference-gating behavior across the translation/tts/avatar chain.

These generally need the local dep stack (`make dev-up`) and multiple service envs,
so they are **not** part of the default per-service `pytest` run and are not yet wired
into CI. Add them here as the platform grows.

## What's here

- `test_e2e_pipeline.py` — ASR end-to-end over the local broker: publishes a
  `media.session.<id>.audio.chunk` and asserts the running asr-service publishes an
  `ai.transcript.segment` back. Gated on `RUN_E2E_TESTS=1` (needs `make dev-up` +
  the service running) so CI and offline dev stay green:

  ```bash
  make dev-up
  cd services/asr-service && uv run uvicorn app.main:app --port 8080
  # (another terminal, repo root)
  RUN_E2E_TESTS=1 uv run pytest tests/test_e2e_pipeline.py -v
  ```

  The root env needs the shared workspace members installed to import them —
  `make bootstrap` / `uv sync --all-packages` does that (plain `uv sync` does not
  install members into a virtual root).

> Scaffold status: one gated cross-service test; the always-on runnable suites are
> the per-service tests under `services/*/tests/` plus each shared lib's own tests.
