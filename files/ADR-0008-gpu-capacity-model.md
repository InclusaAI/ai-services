# ADR-0008: GPU Capacity Model — Autoscaling with Small Always-On Floor

**Status:** Accepted
**Repos affected:** `inclusaai-infra`, `ai-services`, `inclusaai-ml-research`

## Context
`ai-services` runs GPU-backed inference (ASR, sign recognition, avatar pose generation, vision quality) and is likely the platform's largest infrastructure cost driver. `inclusaai-ml-research` runs GPU-backed training workloads. A capacity model was needed before infra committed real spend.

## Decision
- **Production inference GPU capacity**: a small always-on node pool (1–2 nodes) sized for dev/staging and demo traffic, with **autoscaling** node pools for production that scale with active concurrent sessions.
- **Training workloads** (`inclusaai-ml-research`): use **spot/preemptible instances**, since training jobs tolerate interruption far better than live inference does.

## Rationale
- Committing to always-on GPU capacity for production inference before there's real launch traffic is premature spend for a pre-launch platform.
- Live inference (ASR, avatar generation) cannot tolerate the interruption risk of spot/preemptible instances — a mid-session GPU preemption during a live presentation is a real user-facing failure. Training jobs can checkpoint and resume, so the cost savings of spot instances are close to free there.
- A small always-on floor avoids cold-start latency on every dev/staging deploy or demo, without committing to full production-scale always-on cost.

## Consequences
- `inclusaai-infra` builds the autoscaling GPU node pool module (`terraform/modules/gpu-node-pool`) as the default pattern, not always-on as the default with autoscaling as an afterthought.
- `ai-services` needs to expose meaningful scaling signals (active session count, queue depth) that the autoscaler can key off of — this should be an explicit requirement in `ai-services`' service design, not assumed to be free.
- GPU cost should be tracked as a first-class metric from first production deployment, given it's the platform's most significant infra cost driver — feed this into `inclusaai-infra`'s observability milestone.
