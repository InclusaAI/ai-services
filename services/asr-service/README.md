# asr-service

Speech-to-text. Consumes per-session audio and publishes transcript segments that
the rest of the accessibility pipeline (captions, translation, TTS, avatar) builds on.

**This is the reference service** — it is the fullest of the seven and the one to
copy when fleshing out the others. Its wiring (config → pipeline → engine →
pre/post-processing, plus the shared FastAPI app + health/metrics) is the template.

## I/O

| | Topic / event key | Payload |
|---|---|---|
| Consumes | `media.session.<id>.audio.chunk` (pattern) | `AudioChunk` |
| Consumes | `accessibility.preference.updated` | `AccessibilityPreferenceUpdated` (handled by the base pipeline) |
| Publishes | `ai.transcript.segment` | `TranscriptSegment` |
| Publishes | `ai.usage.aggregate` (periodic) | `UsageAggregate` (unit = `transcript_segment`) |

Transcripts are **foundational** — every downstream channel derives from them — so
this service does not preference-gate its output (`output_channel = None`). The
leaf services (tts, avatar-pose, translation) do the channel-specific gating.

## Layout

```
app/
  main.py            # ai_core.create_app(...) — FastAPI + health + metrics + lifespan
  config.py          # Settings(BaseServiceSettings): model + ASR specifics
  pipeline.py        # AsrPipeline(BaseInferencePipeline): audio.chunk -> transcript.segment
  preprocessing/     # audio.py  — decode/resample transported audio to PCM
  inference/         # engine.py — AsrEngine (MLflow model; deterministic stub until one is registered)
  models/            # loader.py — thin wrapper over shared model_loading
  postprocessing/    # segments.py — build the TranscriptSegment contract payload
  api/
    rest.py          # POST /v1/transcribe — synchronous debug endpoint (no Kafka)
    grpc_server.py   # streaming ASR servicer skeleton (implements grpc-contracts AsrService)
```

## Run locally

```bash
uv sync
# starts HTTP on :8080 with /healthz /readyz /metrics; consumes Kafka if reachable
uv run uvicorn app.main:app --host 0.0.0.0 --port 8080
```

With no `MODEL_NAME` set (or the model not yet registered in MLflow), the engine
runs in a **deterministic stub mode** so the service is runnable end-to-end before
a real model is promoted through the ADR-0005 evaluation gate.

## Test

```bash
uv run pytest
```
