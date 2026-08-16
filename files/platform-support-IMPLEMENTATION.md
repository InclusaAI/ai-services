# platform-support — Implementation Guide

## 1. Purpose & Scope
Owns **billing and notifications** — supporting platform services that are not on the real-time critical path. Kept separate from `platform-backend` deliberately: these services have different deploy cadence and risk profile (a billing bug is bad, but it doesn't take down a live presentation the way a `session-service` outage would).

## 2. Owned Services
| Service | Responsibility | Data Owned |
|---|---|---|
| `billing-service` | Org plans, subscriptions, invoicing, AI usage metering | `subscriptions`, `invoices`, `usage_records` |
| `notification-service` | Email/push notifications (org invitations, session reminders, export-ready alerts) | `notification_log` (delivery status, not content) |
| `recording-service` | **(added — see ADR-0006)** Synchronized recording assembly from raw media + AI output streams; export generation | `recordings`, `transcript_exports` |
| `analytics-service` | **(added — see ADR-0006)** Consumes `analytics.event.raw` and AI performance/engagement signals; powers PRD Section 4 module 8 dashboards | `analytics_aggregates` (aggregate-only, no per-individual data for engagement metrics) |

**Ownership rationale:** neither `recording-service` nor `analytics-service` mapped cleanly onto the original 10-repo list. Both are non-real-time-critical and supporting in nature — the same operational profile as billing/notifications — so they land here as new modules rather than justifying an 11th repo.

## 3. Tech Stack
- NestJS (TypeScript, Node 20+)
- PostgreSQL + Prisma
- BullMQ (Redis-backed) for notification dispatch and billing job processing (invoice generation, usage aggregation runs)
- Kafka consumer for usage-metering events and notification triggers
- Third-party integrations: payment provider (Stripe or similar — **not yet chosen, flag as gap**), email/push provider (SendGrid/Twilio or similar — **not yet chosen**)

## 4. Folder Structure
```
platform-support/
├── apps/
│   ├── billing-service/
│   └── notification-service/
├── libs/
│   └── internal-shared/
├── docker-compose.dev.yml
└── .github/workflows/
```

## 5. Contracts

### Consumes (Kafka, for usage metering and notification triggers)
- `session.created`, `session.ended` (from `platform-backend`) → billing usage tracking, "session ended, export ready" notification trigger
- `ai.transcript.segment` volume / `ai.avatar.pose.frame` volume — **AI usage metering likely needs aggregated counts, not raw event consumption**; consider whether `ai-services` should publish a periodic `ai.usage.aggregate` summary event rather than `billing-service` consuming every raw AI event directly (much lower Kafka load, cleaner contract)
- Org invitation events (from `identity-service` in `platform-backend`) → `notification-service` sends the invite email

### Publishes
- `billing.invoice.created`, `billing.subscription.updated`
- `notification.dispatch.completed` / `.failed` (for audit/observability, not consumed by other services at MVP)
- `recording.export.ready` → triggers `notification-service` to alert the presenter

### Consumes (recording-service — new)
- Raw media from `realtime-media-backend` (`media.session.*.audio.chunk`, `.video.frame` or a recording-specific raw feed if bandwidth requires a separate topic — confirm with `realtime-media-backend`)
- `ai.transcript.segment`, `ai.avatar.pose.frame`, `ai.translation.result` (from `ai-services`) — same streams `fanout-service` reads, consumed here for offline assembly rather than live relay

### Consumes (analytics-service — new)
- `analytics.event.raw` (from `platform-backend`)
- `ai.engagement.signal.aggregate`, AI performance/latency metrics (from `ai-services`) — recommend `ai-services` publish periodic aggregated summaries here rather than `analytics-service` consuming every raw AI event; keeps Kafka load sane and the contract clean

### Exposes (REST)
- `/billing/*` — plan management, invoice retrieval (consumed by `web-apps` admin surface)
- `/recordings/*` — playback, export download (consumed by `web-apps` presenter/audience apps)
- `/analytics/*` — dashboard data (consumed by `web-apps` admin surface)
- Notification service has no public REST surface at MVP — purely event-driven

## 6. Dependencies on Other Repos
- `@inclusaai/shared-types`, `@inclusaai/shared-auth`, `@inclusaai/kafka-contracts`
- `inclusaai-infra` for deployment
- Depends on `platform-backend`'s `identity-service` for org/user data (via event consumption, not direct DB access — **do not share a database across repos**, even if convenient)

## 7. MVP Milestones
Per PRD Section 15, billing and advanced org features are **not** in MVP scope. Recommend:
1. `notification-service`: basic transactional email only (org invite, password reset) — needed even for MVP auth flows
2. `billing-service`: can be entirely deferred post-MVP unless the MVP includes paid signup — confirm with product before building anything here

## 8. Quality Bar
Standard bar applies. Billing specifically needs: idempotent event processing (usage events must never double-count), audit logging on every billing state change, and reconciliation tooling (ability to recompute usage/invoices from source events if a bug is found — don't treat billing state as the only source of truth, replay from Kafka).

## 9. Decisions (formerly Gaps) — see `inclusaai-docs/docs/adr/`

- **Payment provider → Stripe.** Standard, well-documented, no unusual requirements at MVP (no marketplace/multi-party payments per PRD's deferred billing scope). Revisit only if a specific enterprise customer requires a different invoicing system. See ADR-0009.
- **Email/push provider → SendGrid (or Resend as a lighter alternative).** Same reasoning — not worth agonizing over, pick and move on. See ADR-0009.
- **AI usage metering granularity → aggregated summary events from `ai-services`**, not raw event consumption. `ai-services` publishes a periodic `ai.usage.aggregate` summary rather than `billing-service` consuming every raw AI event — much lower Kafka load, cleaner contract. See ADR-0009.
- **`billing-service` at MVP → scaffold only.** MVP explicitly excludes billing per the PRD; `notification-service`, `recording-service`, and `analytics-service` are the real MVP-relevant work in this repo. `billing-service` can remain an empty, deployable scaffold until paid signup is actually in scope.
