# inclusaai-ml-research — Implementation Guide

## 1. Purpose & Scope
Home for **experimentation, dataset curation, and model development** for InclusaAI's AI capabilities — most critically, sign language recognition and generation, which are the platform's hardest and least-commoditized ML problems. This repo is explicitly separated from `ai-services` per the brief: production code never runs research/notebook code directly. This repo produces **validated, versioned model artifacts**; `ai-services` consumes them.

## 2. Owned Responsibilities
- Dataset acquisition, curation, and versioning (especially sign language corpora — per-language, since ASL/BSL/ISL etc. are distinct languages requiring distinct datasets)
- Model training pipelines (sign recognition, avatar pose/gloss generation, ASR fine-tuning if needed, translation model evaluation)
- Benchmarking and evaluation harnesses
- Model validation gates before promotion to `ai-services`
- MLflow experiment tracking and model registry (the registry itself may be shared infrastructure with `ai-services`, but experiment authorship lives here)

## 3. Tech Stack
- Python, PyTorch, Transformers (same core ML stack as `ai-services`, for consistency when models graduate)
- OpenCV, MediaPipe (sign language landmark extraction, matches `ai-services`' CV pipeline so research findings transfer directly)
- MLflow (experiment tracking + model registry — **this is the seam with `ai-services`**, treat the registry API as a real contract)
- Jupyter notebooks for exploration — but any pipeline intended to run repeatedly (training, evaluation) should be a proper script/module, not a notebook, from early on
- CUDA for GPU training workloads

## 4. Folder Structure
```
inclusaai-ml-research/
├── notebooks/                      # exploratory only — nothing production-critical lives only in a notebook
├── datasets/
│   ├── sign-language/
│   │   ├── asl/
│   │   ├── bsl/
│   │   └── ...                     # explicit per-language structure from day one
│   ├── speech/
│   └── DATASET_CARDS.md            # provenance, licensing, consent documentation per dataset — non-negotiable given this involves human subjects' likeness/movement data
├── training/
│   ├── sign-recognition/
│   ├── avatar-pose-generation/
│   └── asr-finetuning/
├── evaluation/
│   ├── benchmarks/
│   └── reports/
├── mlflow/                         # tracking config, registry promotion scripts
└── environment/
    └── requirements.txt / pyproject.toml
```

## 5. Contracts
No Kafka/gRPC contracts (this repo doesn't run in production). Its contract with `ai-services` is the **MLflow model registry interface**: a model is only consumable by `ai-services` once it's registered with a version tag and has passed the evaluation gate documented in `evaluation/reports/`. Define what "passes the gate" means explicitly (accuracy threshold, latency benchmark, fairness/bias evaluation across signer demographics) before the first model promotion, not after.

## 6. Dependencies on Other Repos
One-directional: `ai-services` depends on this repo's registered model outputs. This repo should not depend on any production repo's code, though it should stay aligned with `ai-services`' inference-time preprocessing (e.g., if `ai-services` uses MediaPipe landmarks at a specific resolution/framerate, research needs to train against the same preprocessing or the model won't transfer cleanly).

## 7. Milestones
Given sign language recognition is flagged as the highest-risk MVP item across other guides in this batch:
1. **Scope decision first**: which sign language(s) for MVP — this blocks dataset acquisition, which blocks everything else here. This is the single most time-sensitive open item in the entire program.
2. Dataset acquisition + `DATASET_CARDS.md` documentation (provenance/consent/licensing) for the chosen language(s)
3. Baseline sign-recognition model (landmark-based sequence model) + evaluation harness
4. Baseline avatar pose/gloss generation — recommend starting with a constrained-vocabulary approach (canned phrase library) as the first production-viable milestone, with full generative gloss synthesis as a later research track, consistent with the phased approach flagged in `ai-services`' guide
5. Promotion pipeline to MLflow registry, consumed by `ai-services`

## 8. Quality Bar
Model evaluation must include: accuracy/latency benchmarks, **fairness evaluation across signer demographics** (skin tone, hand size, signing speed variation — CV models notoriously underperform on underrepresented groups if training data isn't deliberately diverse), and clear versioning so a regression in a promoted model can be traced back to a specific training run.

## 9. Decisions (formerly Gaps) — see `inclusaai-docs/docs/adr/`

- **Sign language scope for MVP → ASL**, matching `ai-services`' decision (ADR-0002). This was an engineering/product call on *which language*; it does **not** substitute for Deaf-community/linguist consultation on *how* that language is represented in training data, gloss structure, and avatar output — that consultation is a prerequisite for dataset work starting, not a parallel nice-to-have. Do not begin large-scale ASL dataset acquisition without it.
- **Dataset licensing/consent → legal review required before any large-scale acquisition.** Human movement/likeness data carries real consent and licensing implications distinct from typical training data (text/image scraping norms don't transfer cleanly to filmed signers). Treat `DATASET_CARDS.md` provenance documentation as a hard gate on using any dataset in training, not retroactive paperwork.
- **Model registry ownership → MLflow hosted as shared infrastructure, owned by `inclusaai-infra`.** Both this repo and `ai-services` consume the same registry rather than each standing up independent infrastructure. See ADR-0005 — sequence this with `inclusaai-infra`'s milestone plan before the first model promotion is expected.
