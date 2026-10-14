# Deploying ai-services on Render

The platform deploys to Render via the [render.yaml](render.yaml) Blueprint in the
repo root. Render builds each inference service from its own Dockerfile (context =
repo root, so `shared/` path-dependencies resolve), preserving the per-service
dependency isolation the monorepo requires.

## What the Blueprint creates

| Resource | Render type | Notes |
|---|---|---|
| 7 inference services | `web` | Each on `:10000`, health check `/healthz`, public `onrender.com` URL |
| mlflow | `pserv` (private) | Model registry; artifacts on a persistent disk; only reachable inside Render's network |
| mlflow-db | `postgres` | MLflow backend store (basic-256mb) |

## Deploy steps

1. Push this branch to your GitHub repo.
2. Render Dashboard → **New → Blueprint** → select the repo + branch (`deploy/setup`).
3. Review the resource list and apply. The first build runs `uv sync --no-dev` per
   service image — expect several minutes.
4. Each service comes up at `https://<name>.onrender.com`:
   - `/` identity, `/docs` Swagger UI, `/healthz`, `/readyz`, `/metrics`
   - asr-service additionally has `/v1/transcribe`, `/v1/transcribe/file`, `/v1/formats`

## Kafka — runs on Render itself

The Blueprint includes a **single-node Redpanda broker** (Kafka-protocol
compatible) as a *private service*: reachable only on Render's private network
at `redpanda:10000`, never exposed publicly. Each inference service gets
`KAFKA_BOOTSTRAP_SERVERS=redpanda:10000` automatically. Topics auto-create on
first publish (dev-style); provision explicitly for production.

To use a managed external Kafka instead (Upstash / Redpanda Cloud / Confluent
Cloud), delete the `redpanda` service from the Blueprint and set
`KAFKA_BOOTSTRAP_SERVERS` (+ `KAFKA_USERNAME` / `KAFKA_PASSWORD`, which switch
the shared clients to SASL) on each service in the dashboard.

Until the broker is reachable, every service boots in **offline stub mode**:
HTTP surface + deterministic stub inference, no event flow (by design — see
[.env.example](.env.example)).

## Costs / limits to know

- Free web-service plans sleep after inactivity and have 512 MB RAM — too small
  for real models. The blueprint pins `starter` (0.5 CPU / 512 MB) — enough for
  stub mode; use `2c-8g`+ (or Render GPU instances) once real models are loaded.
- `basic-256mb` Postgres is the smallest paid plan; free Postgres expires after
  30 days.
- All 7 services + redpanda + mlflow + postgres = 10 paid instances. Web
  services are pinned at `1c-2g`; redpanda at `2c-4g` (it wants ~2 GB RAM).
  Trim the blueprint to just asr + sign-recognition first if cost matters.

## Observability

`OTEL_EXPORTER_OTLP_ENDPOINT` (also `sync: false`) accepts any hosted OTLP
endpoint, e.g. Grafana Cloud. Leave empty to skip tracing; `/metrics` stays
available per-service regardless.
