# inclusaai-docs — Implementation Guide

## 1. Purpose & Scope
Central home for architecture documentation, API/event contract specs, security documentation, accessibility guidelines, and engineering onboarding. This is also the natural home for **this very set of implementation guides** — once finalized, these 10 documents (or links to them, since each also lives in its owning repo as a README) should be indexed here.

## 2. Owned Content
- Architecture Decision Records (ADRs) — every significant cross-repo decision (SFU vendor choice, database isolation strategy, cloud provider, etc. — including the open Gaps flagged across the other 9 guides) should land here as a formal ADR once resolved
- API documentation: OpenAPI specs for all REST surfaces (aggregated from `platform-backend`, `platform-support`)
- AsyncAPI specs for all Kafka event contracts (source of truth for `@inclusaai/kafka-contracts`, documented here even though the package itself is versioned/published separately)
- Protobuf documentation for gRPC contracts (`@inclusaai/grpc-contracts`)
- Accessibility guidelines and WCAG 2.2 compliance checklists per component/screen type
- Security documentation (threat model, data classification, auth flows)
- Onboarding docs for new engineers per repo

## 3. Tech Stack
- Docusaurus (site generator)
- Markdown/MDX (content)
- OpenAPI + AsyncAPI (spec formats, rendered into the docs site via Docusaurus plugins)
- Protocol Buffers (source docs generated from `.proto` files in `@inclusaai/grpc-contracts`)
- Mermaid (diagrams — architecture flows, pipeline diagrams, matching the style already used in the brief/PRD)

## 4. Folder Structure
```
inclusaai-docs/
├── docs/
│   ├── adr/                        # ADR-0001-sfu-vendor.md, ADR-0002-db-isolation.md, etc.
│   ├── architecture/
│   │   ├── system-overview.md      # the org-wide picture, links out to each repo's implementation guide
│   │   └── event-driven-pipelines.md
│   ├── api-specs/
│   │   ├── openapi/
│   │   ├── asyncapi/
│   │   └── grpc/
│   ├── accessibility/
│   │   ├── wcag-checklist.md
│   │   └── sign-language-scope.md   # tracks which sign languages are supported/planned, per your own accessibility philosophy this needs to be an explicit, visible artifact
│   ├── security/
│   └── onboarding/
│       ├── platform-backend.md
│       ├── realtime-media-backend.md
│       ├── ai-services.md
│       └── ... (one per repo, can literally be the implementation guides you're building now)
├── docusaurus.config.js
└── .github/workflows/
```

## 5. Contracts
Not a service — no Kafka/gRPC contracts of its own. Its "contract" with the rest of the org is being the **canonical index**: every other repo's README should link back here for the full architecture picture, and this repo should link out to each repo's own implementation guide rather than duplicating it (avoid two sources of truth drifting apart).

## 6. Dependencies on Other Repos
Pulls OpenAPI/AsyncAPI/proto spec files from `@inclusaai/shared-types`, `@inclusaai/kafka-contracts`, `@inclusaai/grpc-contracts` publish pipelines (ideally auto-synced via CI whenever those packages publish a new version, not manually copy-pasted).

## 7. Milestones
1. Stand this up **now**, in parallel with the other 9 — it's the natural landing place for the Gaps sections flagged across every guide in this batch. Turn each "Gaps to resolve" list into a tracked ADR-in-progress.
2. System overview + architecture diagrams (can largely reuse what's already been drafted in this conversation)
3. Per-repo onboarding docs (the 10 implementation guides)
4. API spec aggregation/auto-sync from published packages
5. Accessibility guidelines + sign-language scope tracker — flagged as a genuinely important artifact, not busywork, given how many other guides in this batch surfaced sign-language-scope as an unresolved product decision

## 8. Quality Bar
Docs-as-code discipline: PR review required for ADRs and architecture docs, broken-link checking in CI, spec files validated (OpenAPI/AsyncAPI linting) before merge so this repo doesn't silently drift out of sync with the actual contracts.

## 9. Decisions (formerly Gaps) — status update

The cross-repo decisions originally flagged as gaps across all 10 implementation guides have now been made and are documented as ADR-0001 through ADR-0010 (see `docs/adr/` and the index below). This repo's first real content pass is effectively already seeded — the remaining open item is:

- **Sync mechanism between published contract packages and this repo's spec docs** — still open. Recommend a webhook-triggered CI job (fires when `@inclusaai/kafka-contracts` or `@inclusaai/grpc-contracts` publish a new version, regenerates the corresponding AsyncAPI/proto docs here automatically) over manual updates, since manual sync will drift within a quarter on a 10-repo org. Track this as ADR-0011 once implemented.

## 10. ADR Index (drafted — see `docs/adr/`)
| ADR | Decision |
|---|---|
| ADR-0001 | SFU vendor: LiveKit |
| ADR-0002 | Sign language MVP scope: ASL, constrained-vocabulary avatar, recognition as first descope candidate |
| ADR-0003 | Database isolation: separate logical DB per service, shared instance |
| ADR-0004 | Design system cross-platform strategy: tokens-only shared package |
| ADR-0005 | Model registry hosting: MLflow owned by `inclusaai-infra` |
| ADR-0006 | Recording & analytics ownership: new services inside `platform-support` |
| ADR-0007 | Video frame sampling rate: 15fps starting point |
| ADR-0008 | GPU capacity model: autoscaling with small always-on floor |
| ADR-0009 | Third-party providers: Stripe (payments), SendGrid (email), aggregated AI usage events |
| ADR-0010 | Real-time transport: socket.io across `platform-backend` and `realtime-media-backend` |
| — | Cloud provider: **still open**, intentionally not forced — see `inclusaai-infra` guide |
