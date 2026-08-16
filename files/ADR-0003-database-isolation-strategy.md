# ADR-0003: Database Isolation Strategy — Separate Logical DB per Service, Shared Instance

**Status:** Accepted
**Repos affected:** `platform-backend`, `platform-support`

## Context
Services within `platform-backend` (`identity-service`, `session-service`, `preference-service`, `presenter-assist-service`) and `platform-support` (`billing-service`, `notification-service`, `recording-service`, `analytics-service`) needed a decision on database topology: one shared database, separate logical databases on shared instance(s), or fully separate database instances per service.

## Decision
Each service gets its **own logical database** (own schema, own credentials, own migrations), on a **shared Postgres instance per environment** (dev/staging/prod).

## Rationale
- A shared database across services recreates the tight coupling the org-level polyrepo split was meant to avoid — a schema change or lock in one service's tables shouldn't be able to affect another service's availability, and cross-service joins should be structurally impossible, not just discouraged by convention.
- Fully separate instances per service is operational overhead not justified at MVP scale — that's 4-8 database instances to provision, monitor, and back up before there's real load data to justify it.
- Separate logical databases on a shared instance gets real isolation (no accidental cross-service queries, independent migration history, independent credentials) without the infra cost of full instance separation.

## Consequences
- `inclusaai-infra`'s Terraform module for managed Postgres provisions one instance per environment with per-service database/credential provisioning built in, not one instance per service.
- If a specific service's load profile genuinely outgrows shared-instance performance later, split that service to its own instance — this is an incremental migration, not a full redesign, because logical isolation is already in place.
- `fanout-service` is unaffected (Redis-only, no persistent database).
