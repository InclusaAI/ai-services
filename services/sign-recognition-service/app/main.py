"""sign-recognition-service entrypoint.

Builds the shared FastAPI app (health, readiness, metrics, structured logging,
tracing) and attaches the sign pipeline to its lifespan plus a debug REST router.

Run with:  uv run uvicorn app.main:app --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

from inclusaai_ai_core import create_app, run

from app.api.rest import build_router
from app.config import settings
from app.pipeline import SignPipeline

pipeline = SignPipeline(settings)
app = create_app(
    settings,
    pipeline=pipeline,
    extra_routers=[build_router(pipeline.engine, settings)],
)


if __name__ == "__main__":
    run(app, settings)
