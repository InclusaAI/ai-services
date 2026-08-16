"""sign-recognition-service entrypoint.

Run with:  uv run uvicorn app.main:app --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

from inclusaai_ai_core import create_app, run

from app.config import settings
from app.pipeline import SignPipeline

pipeline = SignPipeline(settings)
app = create_app(settings, pipeline=pipeline)


if __name__ == "__main__":
    run(app, settings)
