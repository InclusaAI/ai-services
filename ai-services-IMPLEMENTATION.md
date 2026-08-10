# ai-services — Implementation Guide

## 1. Purpose & Scope
Hosts all **production AI inference** for InclusaAI: speech recognition, sign language recognition, translation, speech synthesis, avatar pose generation, and vision quality analysis (framing/lighting/hand-visibility). This repo consumes **only validated, versioned models** — it never runs experimental notebooks or research code directly (that boundary is explicit in the brief: research → validated models → `ai-services` → `platform-backend` → clients).

Each capability is its own independently deployable inference service, since GPU resource needs, scaling patterns, and latency SLAs differ significantly between them (ASR is latency-critical at ~300-800ms; avatar pose generation can tolerate more).

## 2. Owned Services
| Service | Input | Output | Notes |
|---|---|---|---|
| `asr-service` | `media.session.*.audio.chunk` | `ai.transcript.segment` | Streaming, highest latency sensitivity |
| `sign-recognition-service` | `media.session.*.video.frame` | `ai.sign.recognition.result` | MediaPipe landmarks → sequence model; **plan for per-sign-language model variants**, not one model |
| `translation-service` | `ai.transcript.segment` or `ai.sign.recognition.result` | `ai.translation.result` | Text-to-text, multilingual |
| `tts-service` | `ai.translation.result` or `ai.transcript.segment` | `ai.tts.audio.chunk` | Speech synthesis for Deaf→Hearing direction |
| `avatar-pose-service` | `ai.transcript.segment` / `ai.translation.result` | `ai.avatar.pose.frame` | Text/gloss → skeletal pose; highest-bandwidth output contract |
| `vision-quality-service` | `media.session.*.video.frame` | `ai.vision.quality.signal` | Lighting, framing, hand-visibility, signing pace — feeds `presenter-assist-service` |
| `engagement-service` | audience video/interaction signals (aggregate only) | `ai.engagement.signal.aggregate` | **Privacy-critical**: schema must structurally exclude per-individual identifiers, not just by policy |

## 3. Tech Stack
- Python, FastAPI (for any REST/gRPC service wrapper)
- PyTorch + Transformers (model runtime)
- OpenCV + MediaPipe (CV pipeline for sign-recognition and vision-quality)
- ONNX Runtime where inference speed matters more than PyTorch flexibility (candidate: `asr-service`, `vision-quality-service`)
- CUDA for GPU-backed services
- MLflow for model versioning/registry — **this is the seam with `inclusaai-ml-research`**: research validates a model, registers it in MLflow, `ai-services` pulls the registered version, never a raw checkpoint from a notebook
- gRPC servers implementing `@inclusaai/grpc-contracts` interfaces (generated Python stubs)
- Kafka consumers/producers for the streaming pipeline

## 4. Folder Structure
```
ai-services/
├── services/
│   ├── asr-service/
│   ├── sign-recognition-service/
│   ├── translation-service/
│   ├── tts-service/
│   ├── avatar-pose-service/
│   ├── vision-quality-service/
│   └── engagement-service/
├── shared/
│   ├── grpc_stubs/          # generated from @inclusaai/grpc-contracts
│   ├── kafka_clients/       # shared producer/consumer wrappers
│   └── model_loading/       # MLflow model registry client, shared across services
├── pyproject.toml (or per-service, if dependency conflicts require isolation — likely for CUDA versions)
└── .github/workflows/       # separate GPU-runner pipeline per service
```

**Note:** if `asr-service` and `sign-recognition-service` need different CUDA/PyTorch versions, don't force a shared virtualenv — give each service its own `pyproject.toml`/lockfile even though they're siblings in this repo. This is exactly the kind of Python dependency conflict the org-level polyrepo split (ai-services vs platform-backend) was meant to avoid; don't reintroduce it *within* this repo.

## 5. Contracts

### Consumes
- `media.session.*.audio.chunk`, `media.session.*.video.frame` (from `realtime-media-backend`)
- `accessibility.preference.updated` (from `platform-backend`) — **critical**: determines which downstream generation to actually run per session. If no participant has avatar enabled, `avatar-pose-service` shouldn't be doing wasted GPU work. Build preference-awareness into the pipeline early, not as a later optimization.

### Publishes
- `ai.transcript.segment`, `ai.sign.recognition.result`, `ai.translation.result`, `ai.tts.audio.chunk`, `ai.avatar.pose.frame`, `ai.vision.quality.signal`, `ai.engagement.signal.aggregate`

All schemas live in `@inclusaai/kafka-contracts`, versioned. `ai.avatar.pose.frame` is the highest-frequency, most bandwidth-sensitive schema in the platform — version it carefully and load-test the fan-out path before assuming it's production-ready.

## 6. Dependencies on Other Repos
- `@inclusaai/kafka-contracts`, `@inclusaai/grpc-contracts` (both TypeScript and Python packages generated from shared `.proto`/schema source — coordinate publishing so both ecosystems consume matching versions)
- `inclusaai-ml-research` for validated model artifacts via MLflow registry (one-directional: this repo pulls, never pushes experimental code)
- `inclusaai-infra` for GPU node pool provisioning — flag GPU quota/cost early with infra, this is likely your biggest infra cost driver

## 7. MVP Milestones (from PRD Section 15)
1. `asr-service` — live speech transcription (MVP-critical, build first)
2. `avatar-pose-service` — AI sign language avatar (MVP-critical) — **start with a canned-phrase/limited-vocabulary avatar library before attempting full generative pose synthesis**; PRD explicitly scopes MVP to avatar + hand gesture visualization, not full bidirectional generative sign language
3. Hand gesture rendering — likely a simpler subset of `avatar-pose-service`, not a full sign-recognition round trip
4. `sign-recognition-service` (camera→meaning) — PRD includes this in MVP ("Sign language recognition" is listed), but flag this as the highest-risk MVP item given the modeling difficulty — recommend scoping to one sign language, one well-resourced dataset, for MVP
5. `translation-service`, `engagement-service`, full `vision-quality-service` — explicitly deferred to later phases per PRD Section 15/16

## 8. Quality Bar
Beyond the standard bar: **per-model latency and accuracy benchmarks tracked in MLflow**, GPU utilization monitoring, and load testing under concurrent-session fan-out (10 concurrent sessions with 200 participants each generating avatar streams is a very different load profile than 10 sessions with captions only).

## 9. Decisions (formerly Gaps) — see `inclusaai-docs/docs/adr/`

- **Sign language scope for MVP → ASL only.** Largest available labeled dataset ecosystem (WLASL, How2Sign, ASL-LEX), largest existing research base, largest addressable market for US-first education/enterprise/religious org customers. The pluggable model interface stays architecture-level so additional languages are an addition, not a rewrite, per the platform's own scalability goals. This decision still needs Deaf-community/linguist sign-off before dataset work proceeds in `inclusaai-ml-research` — engineering picked the *language*, not the *dataset or training approach*. See ADR-0002.
- **Avatar generation → constrained vocabulary first, not full generative synthesis.** Build the MVP avatar around a fixed library of ~150–300 common presentation/classroom phrases (greetings, transitions, common Q&A, numbers, fingerspelling) rather than full text-to-gloss-to-pose generation. Full generative sign avatar output is still a research-grade problem industry-wide; a well-executed constrained system with a captions fallback for anything outside the vocabulary is honest and shippable. A generative system that produces linguistically wrong sign grammar actively damages trust with the community this product serves. See ADR-0002.
- **Sign recognition (camera→meaning) → candidate for MVP descoping.** This is the harder direction and the highest-risk MVP item in the whole platform. If timeline pressure hits, cut this before cutting avatar generation — recognition failures are more visible/embarrassing live than a limited avatar vocabulary. Recommend shipping MVP as Hearing→Deaf (speech→captions/avatar) first, with Deaf→Hearing via text input as a stopgap, and re-evaluate recognition for a fast-follow release. See ADR-0002.
- **GPU cost model → autoscaling with a small always-on floor**, not always-on capacity. A 1–2 node always-on pool covers dev/staging/demo traffic; production autoscales with concurrent sessions. Training workloads in `inclusaai-ml-research` use spot/preemptible instances, since training tolerates interruption far better than live inference. Joint decision with `inclusaai-infra` — see ADR-0008.
- **Preference-aware pipeline gating is confirmed in scope for this repo.** `ai-services` consumes `accessibility.preference.updated` and skips inference work (e.g., `avatar-pose-service`) when no active participant in a session needs that output. This is not deferred as "someone else's problem" — build it into the pipeline from the first version, not as a later optimization.
