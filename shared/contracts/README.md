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
| `src/inclusaai_contracts/typescript/` | TypeScript interfaces **generated** from the pydantic models (for `web-apps` / `mobile-app`). |

## Regenerate
```
uv run python scripts/gen_contracts.py     # from repo root
```
This generates three artifact sets from the pydantic models in `events.py`:

1. **gRPC stubs** — `grpcio-tools` protoc over `proto/` → `grpc_stubs/`
2. **JSON Schemas** — `model_json_schema()` for every event → `schemas/<event_key>.schema.json`
3. **TypeScript interfaces** — typed interfaces for every model → `typescript/events.ts`

## TypeScript types for frontend

The generated `typescript/events.ts` file contains:
- **Enum definitions** (e.g. `AccessibilityChannel`)
- **Interface definitions** for every event payload (e.g. `TranscriptSegment`, `AvatarPoseFrame`)
- **Nested types** (e.g. `PoseKeypoint`)
- **Event key → type map** (`AiServiceEvents`) for type-safe Kafka consumers
- **Topic name constants** (`AI_TOPICS`) for topic routing

Usage in `web-apps` / `mobile-app`:
```typescript
import type { TranscriptSegment, AvatarPoseFrame, AiServiceEvents } from '@inclusaai/contracts';

// Type-safe event handling:
function handleEvent<K extends keyof AiServiceEvents>(
  topic: K,
  payload: AiServiceEvents[K]
) {
  switch (topic) {
    case 'ai.transcript.segment':
      // payload is TranscriptSegment
      console.log(payload.text);
      break;
    case 'ai.avatar.pose.frame':
      // payload is AvatarPoseFrame
      renderSkeleton(payload.keypoints);
      break;
  }
}
```

## Design note
We keep the pydantic models as the single source of truth and *derive* all artifacts
from them (JSON Schemas, TypeScript types, gRPC stubs) so they can never drift.
The real `@inclusaai/kafka-contracts` package may invert this (schema-first);
adapt the generator when it lands.
