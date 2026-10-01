# platform-backend — Implementation Guide

## 1. Purpose & Scope
Owns the core, non-media backend domain: **identity, sessions/presentations, accessibility preferences, personalized fan-out, and presenter assistance**. This is the largest repo in the org and the one most other repos depend on (directly via REST/gRPC, indirectly via Kafka events it emits).

Per the approved brief: services inside this repo must be **independently buildable/testable/deployable even though they share a repository**. Treat each module below as a distinct deployable unit, not a shared codebase with one entrypoint.

## 2. Owned Services (independently deployable within this repo)
| Service | Responsibility | Data Owned |
|---|---|---|
| `identity-service` | Auth, users, orgs, org invitations, SSO/OIDC | `users`, `organizations`, `org_memberships`, `invitations` |
| `session-service` | Presentations, meetings, join codes/QR, communication mode selection | `presentations`, `sessions`, `join_tokens` |
| `preference-service` | Per-participant accessibility preferences, persisted across sessions/orgs | `accessibility_preferences` |
| `fanout-service` | Redis-materialized personalized WebSocket delivery to clients | no DB — Redis-only, ephemeral |
| `presenter-assist-service` | Consumes engagement/quality signals from `ai-services`, generates live recommendations | `presenter_sessions_insights` (write-through from Kafka) |

**Rule:** each service gets its own NestJS app (`apps/<service>`), own `main.ts`, own health check, own Dockerfile, own Helm values — even though they live in one repo. No service imports another service's module directly; cross-service calls go through REST/gRPC/Kafka only, same as if they were separate repos. This is what "independently deployable within a shared repo" means in practice — internally this repo should look like an Nx or Turborepo workspace.

## 3. Tech Stack
- NestJS (TypeScript, Node 20+)
- PostgreSQL + Prisma (one schema per service, or fully separate databases if you want hard isolation — **decide before first migration**, hard to retrofit)
- Redis (fanout-service state, preference caching, session tokens)
- Kafka (event publish for cross-service/cross-repo consumption)
- gRPC client generated from `@inclusaai/grpc-contracts` (to call `ai-services`)
- REST via OpenAPI-documented controllers (consumed by `web-apps`, `mobile-app`)
- WebSocket Gateway (`fanout-service`) — `socket.io` or raw `ws`, consistent with `realtime-media-backend`'s choice (align this — see Dependencies)

## 4. Folder Structure
```
platform-backend/
├── apps/
│   ├── identity-service/
│   ├── session-service/
│   ├── preference-service/
│   ├── fanout-service/
│   └── presenter-assist-service/
├── libs/
│   └── internal-shared/          # code shared ONLY within this repo — not published
├── prisma/
│   └── schema.prisma (or per-service schema/ subfolders)
├── docker-compose.dev.yml         # postgres, redis, kafka for local dev
├── package.json / turbo.json (or nx.json)
└── .github/workflows/
```

## 5. Contracts

### Consumes (from `@inclusaai/grpc-contracts`)
- `ai-services`: ASR streaming, translation, TTS — called by `session-service`/`presenter-assist-service` where synchronous request/response is needed outside the Kafka pipeline.

### Consumes (Kafka, from `ai-services` and `realtime-media-backend`)
- `ai.transcript.segment`, `ai.sign.recognition.result`, `ai.avatar.pose.frame`, `ai.translation.result`, `ai.vision.quality.signal`, `ai.engagement.signal.aggregate` → `fanout-service` relays personalized subsets to clients; `presenter-assist-service` consumes quality/engagement signals to generate recommendations.
- `media.session.<id>.participant.joined/left` from `realtime-media-backend` → `session-service` tracks live roster.

### Publishes (Kafka, for `ai-services`, `realtime-media-backend`, `platform-support`, `web-apps`/`mobile-app` via fanout)
- `session.created`, `session.updated`, `session.ended`
- `accessibility.preference.updated` — **this is the one AI services care most about**, since it determines which output channels (avatar/captions/gestures/translation) need generating per participant. Define this schema first in `@inclusaai/kafka-contracts`.
- `presenter.assist.recommendation`
- `analytics.event.raw` → consumed downstream (analytics pipeline owner TBD — see Gaps)

### Publishes (REST, OpenAPI, for `web-apps`/`mobile-app`)
- `/auth/*`, `/organizations/*`, `/presentations/*`, `/sessions/*`, `/preferences/*`

## 6. Dependencies on Other Repos
- `@inclusaai/shared-types`, `@inclusaai/shared-auth`, `@inclusaai/kafka-contracts`, `@inclusaai/grpc-contracts` (npm packages, versioned)
- `inclusaai-infra` for Helm charts / deployment config
- Must agree with `realtime-media-backend` on: WebSocket library choice (align `fanout-service` and media signaling), and the `media.session.*` event schema

## 7. MVP Milestones (from PRD Section 15)
1. `identity-service`: auth + org invitations
2. `session-service`: presentation creation, upload metadata, join via QR/code
3. `preference-service`: basic accessibility preference CRUD (captions/avatar/gestures toggle)
4. `fanout-service`: relay `ai.transcript.segment` → captions only (defer avatar/gesture fanout to post-MVP if timeline is tight)
5. `presenter-assist-service`: defer to post-MVP per PRD (not in MVP scope list)

## 8. Quality Bar (per brief Section 9)
Each of the 5 services needs: type checking, unit + integration tests, OpenAPI/AsyncAPI contract validation, structured logging, Prometheus metrics, OpenTelemetry tracing, health checks, graceful shutdown, config validation via a schema (e.g. `zod` or `class-validator` on `ConfigModule`), and its own Dockerfile + CI/CD stage.

## 9. Decisions (formerly Gaps) — see `inclusaai-docs/docs/adr/`

- **Database isolation → separate logical database per service, shared Postgres instance.** Not one shared database (a schema change in `session-service` shouldn't be able to lock a table `preference-service` reads), but not separate instances either at MVP scale — that's operational overhead you don't need yet. Each service gets its own database/credentials on a shared Postgres instance per environment; migrations run per-service, no cross-service joins possible even by accident. Revisit separate instances only if one service's load genuinely demands it (`fanout-service` is Redis-only, so this really only affects the other 4). See ADR-0003.
- **`analytics.event.raw` consumption → owned by a new `analytics-service` inside `platform-support`**, not a new repo. Not real-time-critical, same operational profile as billing/notifications. See ADR-0006.
- **WebSocket library → `socket.io`**, matched with `realtime-media-backend`'s signaling layer. Reconnection handling and room/namespace support (useful for per-session fan-out grouping) aren't worth hand-rolling on top of raw `ws`, especially given live events are exactly the scenario where a participant's connection drops mid-presentation. See ADR-0010.
