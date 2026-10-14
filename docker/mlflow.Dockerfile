# MLflow tracking server + model registry for the Render deployment.
#
# Render runs this as a private service (pserv, runtime: image) built from this
# Dockerfile. The MLflow base image lacks Postgres/S3 drivers, so we add
# psycopg2-binary (backend store) and boto3 (artifact access) here instead of
# shelling out to pip at container start.
#
# Configuration comes from env vars set in render.yaml:
#   DATABASE_URL  — Render Postgres connection string (fromDatabase reference)
#   PORT          — Render injects this; MLflow binds to it (default 5000)
#   MLFLOW_ARTIFACT_ROOT — persistent-disk path for artifact storage
FROM ghcr.io/mlflow/mlflow:v2.16.2

RUN pip install --no-cache-dir psycopg2-binary boto3

ENV MLFLOW_ARTIFACT_ROOT=/var/data/mlflow-artifacts

CMD ["sh", "-c", "mkdir -p ${MLFLOW_ARTIFACT_ROOT} && \
  exec mlflow server \
  --host 0.0.0.0 --port ${PORT:-5000} \
  --backend-store-uri ${DATABASE_URL:-sqlite:///${MLFLOW_ARTIFACT_ROOT}/mlflow.db} \
  --default-artifact-root ${MLFLOW_ARTIFACT_ROOT} \
  --serve-artifacts"]
