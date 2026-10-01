# inclusaai-infra — Implementation Guide

## 1. Purpose & Scope
Owns all infrastructure-as-code and CI/CD scaffolding shared across the org: Terraform, Kubernetes manifests, Helm charts, and reusable GitHub Actions workflows. This repo is intentionally **cloud-provider-agnostic** for now per your input — structure it so provider-specific modules are isolated and swappable rather than baked into every layer, since that decision is still open.

## 2. Owned Responsibilities
- Terraform modules for core infra: networking, Kubernetes cluster(s), managed Postgres/Redis/Kafka (or self-hosted equivalents), object storage, secrets management
- Kubernetes namespace/cluster topology across Development → Staging → Production
- Helm charts — one per deployable service across all repos (charts live here, not duplicated per app repo, so infra changes don't require touching 10 repos)
- Reusable GitHub Actions workflow templates (lint/test/build/scan/publish/deploy/rollback) that each app repo's `.github/workflows/` calls into
- Observability stack: Prometheus, Grafana, OpenTelemetry collector config, centralized logging pipeline

## 3. Tech Stack
- Terraform (modularized, provider-agnostic where possible — isolate AWS/GCP/Azure-specific resources behind a clean module boundary so the eventual provider decision doesn't require a full rewrite)
- Kubernetes + Helm
- Docker (base images, if you standardize a Node base image and a Python/CUDA base image org-wide — recommended, reduces image bloat and CVE surface across 10 repos)
- GitHub Actions (reusable workflows / composite actions)
- OpenTelemetry, Prometheus, Grafana

## 4. Folder Structure
```
inclusaai-infra/
├── terraform/
│   ├── modules/
│   │   ├── networking/
│   │   ├── kubernetes-cluster/
│   │   ├── managed-postgres/
│   │   ├── managed-redis/
│   │   ├── managed-kafka/          # or self-hosted Strimzi module if not using a managed offering
│   │   ├── object-storage/
│   │   └── gpu-node-pool/          # dedicated module — ai-services' GPU needs are a distinct cost/scaling concern
│   └── envs/
│       ├── dev/
│       ├── staging/
│       └── prod/
├── helm/
│   ├── platform-backend/           # sub-charts per service (identity, session, preference, fanout, presenter-assist)
│   ├── realtime-media-backend/
│   ├── ai-services/                # sub-charts per inference service, GPU resource requests/limits set here
│   ├── platform-support/
│   ├── web-apps/
│   └── mobile-app/                 # CD to app stores, not Helm — separate pipeline definition
├── k8s/
│   └── base/ (namespaces, network policies, RBAC)
├── github-actions/
│   ├── workflows/                  # reusable workflow_call templates
│   └── actions/                    # composite actions (e.g., "build-and-scan-node-image")
├── observability/
│   ├── prometheus/
│   ├── grafana-dashboards/
│   └── otel-collector-config/
└── base-images/
    ├── node-base/
    └── python-cuda-base/
```

## 5. Contracts
This repo doesn't consume/publish Kafka events — its "contract" with other repos is the **Helm chart interface** (values.yaml schema each service must conform to) and the **reusable CI workflow interface** (what inputs each app repo's workflow must provide: build context, test command, image name, deploy target).

Publish a short `CONTRACT.md` here documenting: required labels/annotations on every deployment, required health check endpoints (`/healthz`, `/readyz`), required metrics endpoint (`/metrics`), and required environment variable naming conventions — every other repo's implementation guide should point back to this rather than each repo inventing its own convention.

## 6. Dependencies on Other Repos
This repo is depended *on* by all 6 application repos, and has no reverse dependency — keep it that way. It should never import application-specific business logic.

## 7. Milestones
1. Dev environment: local `docker-compose` equivalents already live in each app repo per their own guides — this repo's first job is **Staging**, not local dev
2. Base Kubernetes cluster + namespace topology (Dev/Staging/Prod)
3. Reusable CI workflows — build these *before* app teams need to write their own from scratch, or you'll get 10 divergent pipelines
4. Helm charts for MVP-critical services first: `platform-backend` (session/preference/fanout), `realtime-media-backend`, `ai-services` (asr + avatar-pose), `web-apps` (presenter + audience)
5. GPU node pool provisioning — coordinate timing tightly with `ai-services`, this is likely the longest lead-time infra item (quota requests, cost approval)
6. Observability stack — stand up early enough that the MVP services aren't flying blind in staging

## 8. Quality Bar
Terraform: `plan` required in CI on every PR, `apply` gated behind manual approval for staging/prod. Helm: chart linting + a `helm template` dry-run diff in CI. All base images: vulnerability scanning (Trivy or similar) as a required CI check, not optional.

## 9. Decisions (formerly Gaps) — see `inclusaai-docs/docs/adr/`

- **Cloud provider — still genuinely open, deliberately not decided here.** This depends on existing team expertise, committed spend/credits, and org preference more than a technical call that can be made from architecture alone. Provider-agnostic module structure buys time but doesn't eliminate the need to choose — recommend timeboxing this decision explicitly rather than letting it drift, since it's the biggest blocker to real (non-scaffold) Terraform work.
- **Managed vs. self-hosted Kafka — defer to the cloud provider decision**, since this is usually provider-coupled (MSK on AWS, Confluent Cloud as provider-agnostic managed option, self-hosted Strimzi if avoiding vendor lock-in). Keep the `managed-kafka` module's interface stable regardless of which is chosen underneath.
- **GPU cost model → autoscaling with a small always-on floor**, not always-on capacity. A 1–2 node always-on pool covers dev/staging/demo; production autoscales with concurrent sessions; `inclusaai-ml-research` training workloads use spot/preemptible instances. Build the autoscaling module first rather than defaulting to always-on because it's simpler to configure. Joint decision with `ai-services` — see ADR-0008.
- **MLflow model registry hosting → owned by this repo as shared infrastructure**, consumed by both `ai-services` and `inclusaai-ml-research`. Neither AI repo should be independently standing up registry infrastructure. See ADR-0005.
