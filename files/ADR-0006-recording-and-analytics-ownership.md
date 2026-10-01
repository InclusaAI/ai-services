# ADR-0006: Recording & Analytics Service Ownership — New Modules in `platform-support`

**Status:** Accepted
**Repos affected:** `platform-support`, `realtime-media-backend`, `platform-backend`, `ai-services`

## Context
Two capabilities described in the PRD — synchronized recording/playback/export (Section 13) and presentation/audience/AI-performance analytics (Section 4, module 8) — did not map cleanly onto any of the original 10 repos. Neither `realtime-media-backend` (produces raw media only) nor `platform-backend` (real-time-critical core domain) was a natural fit, and neither capability is real-time-critical enough, nor different enough in team ownership or deploy cadence, to justify an 11th repo.

## Decision
Add two new services inside the existing `platform-support` repo:
- **`recording-service`** — consumes raw media from `realtime-media-backend` plus AI output streams from `ai-services` (the same streams `fanout-service` relays live), assembles synchronized recordings, and generates exports (MP4, PDF transcript, DOCX transcript, SRT captions, JSON session data).
- **`analytics-service`** — consumes `analytics.event.raw` from `platform-backend` and aggregated AI performance/engagement signals from `ai-services`, and powers the analytics dashboards.

## Rationale
- Both are non-real-time-critical, supporting-in-nature services — the same operational profile as the billing and notification services `platform-support` already owns.
- Avoids repo sprawl: an 11th repo would need its own CI/CD, on-call ownership, and versioning discipline for a service whose deploy cadence and team ownership don't actually differ meaningfully from what's already in `platform-support`.

## Consequences
- `platform-support`'s scope and MVP relevance both increase — `recording-service` in particular is MVP-critical per PRD Section 15 ("session recording, transcript export"), so this repo is no longer "safely deferrable" as a whole, only `billing-service` within it is.
- AI usage/engagement metering should be published as periodic aggregated summary events from `ai-services` (see ADR-0009) rather than `analytics-service` consuming every raw AI event, to control Kafka load.
- `recording-service`'s raw media consumption needs a schema decision with `realtime-media-backend`: reuse the existing `media.session.*.audio.chunk`/`.video.frame` topics, or introduce a dedicated recording-specific feed if bandwidth/retention requirements differ from the live pipeline's needs. Track as a follow-up if not resolved before implementation starts.
