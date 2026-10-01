# ADR-0005: Model Registry Hosting — MLflow Owned by `inclusaai-infra`

**Status:** Accepted
**Repos affected:** `inclusaai-infra`, `ai-services`, `inclusaai-ml-research`

## Context
`inclusaai-ml-research` trains and validates models; `ai-services` consumes validated, versioned model artifacts in production. MLflow was the chosen tracking/registry tool, but it was unclear whether it should be hosted as shared platform infrastructure or stood up independently by one or both AI repos.

## Decision
MLflow (tracking + model registry) is **shared infrastructure, owned and hosted by `inclusaai-infra`**. Both `inclusaai-ml-research` (writes: experiment tracking, model registration) and `ai-services` (reads: pulls registered, versioned models) consume the same instance.

## Rationale
- Avoids two AI repos independently standing up and maintaining overlapping infrastructure.
- Keeps the research→production model promotion path a real, auditable contract (a model is only consumable by `ai-services` once registered with a version tag that has passed the evaluation gate documented in `inclusaai-ml-research`), rather than an informal handoff.
- Matches the existing pattern where `inclusaai-infra` owns cross-cutting operational concerns (Kafka, Postgres, Redis, observability) rather than individual repos each managing their own.

## Consequences
- `inclusaai-infra`'s milestone plan needs to include MLflow provisioning early enough that it doesn't block `inclusaai-ml-research`'s first model promotion or `ai-services`' first production model pull.
- Registry access control and versioning conventions (what "passes the gate" means — accuracy threshold, latency benchmark, fairness/bias evaluation across signer demographics per `inclusaai-ml-research`'s quality bar) should be documented in `inclusaai-docs` as the formal promotion contract between the two repos.
