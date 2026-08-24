# ai-services

InclusaAI's production **AI inference platform**: a Python monorepo of seven
independently-deployable inference microservices that turn a live media session into
real-time accessibility outputs — captions, sign-language recognition, translation,
speech, signing-avatar poses, presenter quality nudges, and privacy-safe engagement
signals.

Services communicate over Kafka with typed payloads; they pull models from an MLflow
registry (never raw checkpoints); and they only do work a participant actually needs
(preference-aware gating). Every service also runs a deterministic **offline stub**
when no model is registered, so the whole platform is runnable and testable with no
GPU, no MLflow, and no Kafka.

> **Authoritative spec:** [ai-services-IMPLEMENTATION.md](ai-services-IMPLEMENTATION.md).
> Supporting: [Stack.md](Stack.md), [Structure.text](Structure.text),
> [Architecure.md](Architecure.md), and the ADRs (see [below](#adrs)).

## Event flow

```
                       media.session.<id>.audio.chunk ─► asr-service ─────────► ai.transcript.segment
                                                                                     │
   media.session.<id>.video.frame ─┬─► sign-recognition-service ─► ai.sign.recognition.result
                                   └─► vision-quality-service ───► ai.vision.quality.signal
                                                                                     │
   ai.transcript.segment ─┬─► translation-service ─► ai.translation.result ─► tts-service ─► ai.tts.audio.chunk
                          └─► avatar-pose-service ─► ai.avatar.pose.frame
   media.session.<id>.participant.{joined,left} ─► engagement-service ─► ai.engagement.signal.aggregate  (periodic)
   (every service) ──────────────────────────────────────────────────► ai.usage.aggregate               (periodic)
```

## Services

| Service | Consumes | Publishes | Preference-gated | Model |
|---|---|---|---|---|
| [asr-service](services/asr-service/) *(reference)* | `media.*.audio.chunk` | `ai.transcript.segment` | no (foundational) | `asr-whisper` |
| [sign-recognition-service](services/sign-recognition-service/) | `media.*.video.frame` | `ai.sign.recognition.result` | no (foundational) | `sign-recognition-asl` |
| [translation-service](services/translation-service/) | `ai.transcript.segment` | `ai.translation.result` | yes — `TRANSLATION` | `translation-nllb` |
| [tts-service](services/tts-service/) | `ai.translation.result` | `ai.tts.audio.chunk` | yes — `TTS` | `tts-vits` |
| [avatar-pose-service](services/avatar-pose-service/) | `ai.transcript.segment` | `ai.avatar.pose.frame` | yes — `AVATAR` | vocab (model optional) |
| [vision-quality-service](services/vision-quality-service/) | `media.*.video.frame` | `ai.vision.quality.signal` | no | heuristic (model optional) |
| [engagement-service](services/engagement-service/) | `media.*.participant.*` | `ai.engagement.signal.aggregate` | no | none (aggregation) |

## Layout

```
ai-services/
├── pyproject.toml            # uv WORKSPACE root (members: shared/*) + ruff/mypy/pytest config
├── Makefile                  # bootstrap / gen-contracts / lint / typecheck / test / dev-up
├── docker-compose.dev.yml    # redpanda (Kafka), MLflow + postgres, MinIO (S3), OTel collector
├── .env.example              # dev config; endpoints match the compose file
├── shared/                   # uv workspace members — pure-Python shared libs (one lockfile)
│   ├── contracts/            # LOCAL PLACEHOLDER for @inclusaai/{kafka,grpc}-contracts
│   ├── ai_core/              # BaseInferencePipeline, service/app factory, config, health, preferences, scaling
│   ├── telemetry/            # structlog logging, Prometheus /metrics, OTel tracing
│   ├── kafka_clients/        # aiokafka consumer/producer wrappers, topics, usage aggregation
│   ├── model_loading/        # MLflow registry read-by-version + benchmarking
│   ├── utils/                # small shared helpers
│   ├── sign_vocab/           # closed constrained ASL vocabulary — phrases + fingerspelling + skeleton (avatar-pose ⇄ sign-recognition)
│   └── pose_tools/           # pose-format (.pose) interchange: Pose ⇄ 51-pt skeleton ⇄ wire keypoints (both sign services)
├── services/                 # 7 STANDALONE uv projects (own pyproject.toml + uv.lock + Dockerfile)
├── docker/                   # python-cuda-base.Dockerfile (GPU base) + OTel config
├── scripts/                  # gen_contracts.py, bootstrap.sh, dev_up.sh
├── models/                   # never committed — pulled from MLflow (see models/README.md)
├── tests/                    # cross-service / integration tests (see tests/README.md)
└── .github/workflows/        # shared.yml + one path-scoped workflow per service
```

### Why services aren't workspace members

The shared libs are a single `uv` workspace (pure Python, one lockfile — fine to
share). Each **service is a standalone `uv` project** with its own `uv.lock`, kept
*out* of the workspace and depending on the shared libs via editable path sources:

```toml
[tool.uv.sources]
inclusaai-ai-core = { path = "../../shared/ai_core", editable = true }
```

This is deliberate: services may need mutually incompatible CUDA / PyTorch stacks, so
they must never be forced to share one resolver environment
([IMPLEMENTATION §4](ai-services-IMPLEMENTATION.md)).

## Quickstart

Requires [`uv`](https://docs.astral.sh/uv/); Docker only for the local dep stack.

```bash
# 1. shared workspace + tooling, contract stubs/schemas, then every service
make bootstrap                 # == uv sync; gen-contracts; (per service) uv sync
                               #   on Windows without make: bash scripts/bootstrap.sh

# 2. run a service (offline stub — no model/Kafka/GPU needed to boot)
#    With no broker reachable, the pipeline starts OFFLINE (consume/publish loop
#    skipped) and just serves its HTTP surface; the engine runs its model stub.
cd services/asr-service && uv run uvicorn app.main:app --port 8080
curl localhost:8080/healthz    # -> 200 ;  /readyz  /metrics  also live

# 3. quality gates
make lint                      # ruff
make typecheck                 # mypy
make test                      # pytest across shared + each service

# 4. local dependencies (Kafka/MLflow/MinIO/OTel) when you want the full loop
make dev-up                    # docker compose -f docker-compose.dev.yml up -d
make dev-down
```

## Cross-cutting behavior (in the shared libs, used by every pipeline)

| Concern | Where | Notes |
|---|---|---|
| `/healthz` `/readyz` `/metrics` | `ai_core` + `telemetry` | readiness flips on pipeline start |
| Preference-aware gating | `ai_core.preferences` | skip inference when no participant needs the output; **fail-open** when the session is unknown |
| Scaling signals (`active_sessions`, `queue_depth`) | `ai_core` gauges | GPU autoscaler inputs ([ADR-0008](files/ADR-0008-gpu-capacity-model.md)) |
| Periodic `ai.usage.aggregate` | `kafka_clients.usage` | billing ([ADR-0009](files/ADR-0009-third-party-providers.md)) |
| Model pull by version/stage | `model_loading` | read-only; never a raw checkpoint ([ADR-0005](files/ADR-0005-model-registry-ownership.md)) |
| Structured logging + OTel tracing | `telemetry` | JSON logs; OTLP traces |

## Contracts (placeholder)

`shared/contracts/` is a **local placeholder** for the not-yet-present
`@inclusaai/kafka-contracts` and `@inclusaai/grpc-contracts` packages. The pydantic
models in `events.py` are the single source of truth; JSON Schemas and gRPC stubs are
*generated* from them:

```bash
make gen-contracts             # uv run python scripts/gen_contracts.py
```

Keep the `inclusaai_contracts` import path stable when the real packages land — see
[shared/contracts/README.md](shared/contracts/README.md).

## ADRs

- [ADR-0002 — sign-language MVP scope](ADR-0002-sign-language-mvp-scope.md) *(root copy is the accepted one: recognition stays in MVP; ASL only)*
- [ADR-0005 — model-registry ownership](files/ADR-0005-model-registry-ownership.md)
- [ADR-0007 — video-frame sampling rate](files/ADR-0007-video-frame-sampling-rate.md) *(15fps starting point)*
- [ADR-0008 — GPU capacity model](files/ADR-0008-gpu-capacity-model.md)
- [ADR-0009 — third-party providers](files/ADR-0009-third-party-providers.md)

## Missing docs (referenced by the guides, not yet in this repo)

The scaffold uses placeholders / sensible defaults for these; replace when available:

- **`@inclusaai/kafka-contracts`** — canonical event payload schemas.
- **`@inclusaai/grpc-contracts`** — canonical `.proto` service defs + stubs.
- **`inclusaai-infra` `CONTRACT.md`** — labels/annotations, health/metrics + env-var conventions, base-image contract.
- **PRD** (referenced as "PRD §13/15/16") — only summarized in the guide.
- **MLflow promotion-gate definition** (accuracy/latency/fairness thresholds) — lives in `inclusaai-docs` per ADR-0005.
