# ADR-0009: Third-Party Provider Selection — Stripe, SendGrid, Aggregated AI Usage Events

**Status:** Accepted
**Repos affected:** `platform-support`, `ai-services`

## Context
`platform-support`'s `billing-service` and `notification-service` needed payment and email/push provider decisions, and `billing-service`'s AI usage metering needed a decision on consumption granularity from `ai-services`' event stream.

## Decision
- **Payment provider: Stripe.**
- **Email/push provider: SendGrid** (Resend acceptable as a lighter-weight alternative if preferred at implementation time).
- **AI usage metering: `ai-services` publishes periodic aggregated summary events** (`ai.usage.aggregate`) rather than `billing-service` consuming every raw AI inference event directly.

## Rationale
- Stripe and SendGrid are standard, well-documented choices with no unusual requirements driving a different pick — the MVP scope has no marketplace/multi-party payment complexity per the PRD's deferred billing scope, so this isn't a decision worth extensive evaluation time.
- Raw per-event usage consumption for billing would meaningfully increase Kafka load across the whole platform (every transcript segment, every avatar frame) for a use case that only needs periodic counts — aggregated summary publishing keeps the contract clean and the load sane.

## Consequences
- `notification-service` and `billing-service` integrate against these providers' SDKs directly; no abstraction layer needed at this scale unless a specific customer requirement forces a provider change later.
- `ai-services` needs to implement periodic usage aggregation and publish `ai.usage.aggregate` — this should be scoped as part of each inference service's implementation, not bolted on later once billing-service needs it.
- Given MVP explicitly excludes billing per the PRD, this ADR's `billing-service` implications are lower urgency than the `notification-service` implications, which are needed for MVP auth flows (org invitation emails).
