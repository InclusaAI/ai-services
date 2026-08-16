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

> Scaffold status: placeholder. The runnable tests today are the per-service suites
> under `services/*/tests/`.
