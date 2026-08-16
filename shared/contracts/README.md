# inclusaai-contracts (LOCAL PLACEHOLDER)

> ⚠️ **This is a placeholder.** In production these definitions come from two
> shared, versioned, cross-ecosystem packages that are **not yet present in this
> repo** (see the repo README "Missing docs"):
> - `@inclusaai/kafka-contracts` — Kafka event payload schemas
> - `@inclusaai/grpc-contracts` — gRPC `.proto` service definitions + generated stubs
>
> When those packages are published, replace this package's contents with the
> generated Python bindings and keep the import path (`inclusaai_contracts`) stable.

## What lives here
| Path | Purpose |
|---|---|
| `src/inclusaai_contracts/events.py` | **Source of truth** — pydantic v2 models for every Kafka payload this platform consumes/publishes. |
| `src/inclusaai_contracts/schema_registry.py` | logical-event-key → model map, plus `json_schema()` / `validate()` helpers. |
| `proto/inclusaai/ai/v1/*.proto` | Placeholder gRPC service defs (ASR streaming, translation, TTS) consumed by `platform-backend`. |
| `src/inclusaai_contracts/grpc_stubs/` | Generated `*_pb2.py` / `*_pb2_grpc.py` land here (git-ignored). |
| `src/inclusaai_contracts/schemas/` | JSON Schemas **generated** from the pydantic models (git-ignored). |

## Regenerate
```
uv run python scripts/gen_contracts.py     # from repo root
```
This (1) runs `grpcio-tools` protoc over `proto/` → `grpc_stubs/`, and (2) dumps
`model_json_schema()` for every event into `schemas/`.

## Design note
We keep the pydantic models as the single source of truth and *derive* the JSON
Schemas from them (rather than hand-maintaining parallel `.json` files) so the two
can never drift. The real `@inclusaai/kafka-contracts` package may invert this
(schema-first); adapt the generator when it lands.
