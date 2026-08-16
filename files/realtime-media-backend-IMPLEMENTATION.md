# realtime-media-backend — Implementation Guide

## 1. Purpose & Scope
Owns **WebRTC ingest, signaling, and real-time media session management**. This is the repo where presenter audio/video (and, for sign-language presenters, camera input) enters the system. It is deliberately separated from `platform-backend` because media/signaling has a different latency profile, scaling pattern (often needs to scale with concurrent media sessions, not request volume), and — per the brief — may later warrant a Go component, though **not at MVP**.

This repo does **not** do any AI inference. It captures, relays, and forwards raw/lightly-processed media into Kafka for `ai-services` to consume. Keep that boundary hard — if ASR or CV logic starts leaking into this repo, the separation of concerns breaks.

## 2. Owned Responsibilities
- WebRTC signaling (offer/answer/ICE candidate exchange)
- SFU integration (LiveKit or mediasoup — pick one for MVP, don't abstract both prematurely)
- Media session lifecycle (join/leave, reconnect handling, simulcast/quality adaptation)
- Chunking and publishing raw audio/video to Kafka for AI consumption
- Recording capture hooks (raw media only — actual recording storage/export lives conceptually under Recording & Playback, likely a `platform-support` or future module — see Gaps)

## 3. Tech Stack
- NestJS (TypeScript, Node 20+) for signaling/session logic
- **LiveKit** (decided — see Section 9). Wrapped behind the internal `SfuAdapter` interface regardless, so mediasoup remains a viable later migration if cost/control needs change.
- WebSockets for signaling
- Kafka producer for raw media chunk publishing
- Redis for ephemeral media-session state (which SFU node, participant roster, ICE state)
- gRPC (consumes `@inclusaai/grpc-contracts` only if calling `ai-services` synchronously for anything — unlikely at MVP, this repo should be Kafka-producer-only for AI handoff)

## 4. Folder Structure
```
realtime-media-backend/
├── src/
│   ├── signaling/          # WebSocket gateway, offer/answer/ICE
│   ├── media-session/      # session lifecycle, roster, reconnect logic
│   ├── sfu-adapter/        # LiveKit/mediasoup integration, swappable interface
│   ├── kafka-producers/    # audio/video chunk publishers
│   └── config/
├── docker-compose.dev.yml  # local SFU + kafka + redis
├── Dockerfile
└── .github/workflows/
```

**Design note:** wrap the SFU behind an internal `SfuAdapter` interface even if you only implement LiveKit at MVP. This is the one place in the platform most likely to change vendors (self-hosting cost vs. managed service trade-offs shift over time), and per the brief's "extensible AI providers and sign language engines" philosophy, the same discipline applies here.

## 5. Contracts

### Publishes (Kafka, for `ai-services`)
- `media.session.<sessionId>.audio.chunk` — raw/opus-encoded audio chunks, tagged with `speakerId`, `sequence`, `timestamp`
- `media.session.<sessionId>.video.frame` — sampled video frames (not full video stream — sample at whatever rate CV models need, likely far lower than full framerate, to control Kafka throughput)
- `media.session.<sessionId>.participant.joined` / `.left` — for `platform-backend`'s `session-service` to track live roster

### Consumes
- `session.created` / `session.ended` (from `platform-backend`) — to know when to provision/tear down a media session
- `accessibility.preference.updated` (from `platform-backend`) — **only if** camera framing/quality feedback needs to be routed back to a specific presenter's client (e.g., "move into frame" prompts from `ai.vision.quality.signal`, relayed back through signaling rather than the general fanout path)

### Exposes (REST/WebSocket, for `web-apps`/`mobile-app`)
- Signaling endpoints for join/leave/renegotiate
- Media session status/health

## 6. Dependencies on Other Repos
- `@inclusaai/shared-types`, `@inclusaai/kafka-contracts`
- `inclusaai-infra` for Helm/K8s (media workloads often need dedicated node pools/network policies — flag this explicitly to infra, it's not a generic stateless service)
- Must jointly define `media.session.<id>.audio.chunk` / `.video.frame` schemas with `ai-services` **before either side builds against them** — this is the highest-traffic contract in the whole platform

## 7. MVP Milestones
1. Signaling + single-presenter, single-SFU-room media session
2. Audio chunk publishing to Kafka (this unblocks `ai-services` ASR work in parallel)
3. Video frame sampling + publishing (unblocks sign-recognition work in parallel — can trail audio by a sprint since MVP prioritizes speech transcription first per PRD Section 15)
4. Physical/Virtual/Hybrid mode support (QR/code joining is `session-service`'s job; this repo just needs to accept the resulting join tokens)
5. Basic reconnect handling (non-negotiable for live events — a dropped Wi-Fi packet shouldn't kill a presentation)

## 8. Quality Bar
Same baseline as all services (type checking, tests, health checks, tracing, graceful shutdown) **plus** media-specific concerns: connection quality metrics (packet loss, jitter, RTT) exported to Prometheus, and load testing for concurrent-session scaling before any real event.

## 9. Decisions (formerly Gaps) — see `inclusaai-docs/docs/adr/`

- **SFU → LiveKit.** Self-hosting mediasoup means also maintaining SFU infra, TURN servers, and scaling logic on top of everything else on this roadmap. LiveKit gets to a working demo in weeks and has built-in recording hooks (feeds directly into the recording decision below). The `SfuAdapter` interface stays in place so this isn't a one-way door — migrate later only if LiveKit Cloud cost becomes a real problem at scale. See ADR-0001.
- **Video frame sampling rate → start at 15fps** for sign-recognition input. Full 30/60fps into Kafka is unnecessary bandwidth; MediaPipe-based sign recognition pipelines are commonly built around ~15fps. Treat this as a starting point, not a fixed constraint — let the `ai-services` sign-recognition team push it higher only if real accuracy numbers demand it. See ADR-0007.
- **Recording capture ownership → `recording-service` inside `platform-support`.** This repo (`realtime-media-backend`) publishes raw media and stays out of assembly/storage logic. `recording-service` subscribes to the same Kafka topics `fanout-service` reads (`ai.transcript.segment`, `ai.avatar.pose.frame`, etc.) plus this repo's raw media, and assembles synchronized recordings + handles export formats (MP4/PDF/DOCX/SRT/JSON per PRD Section 13). See ADR-0006.
