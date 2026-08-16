from __future__ import annotations

import base64

import pytest

from inclusaai_contracts.events import VideoFrame

from app.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        service_name="sign-recognition-test",
        model_name=None,
        otel_exporter_otlp_endpoint=None,
    )


@pytest.fixture
def video_frame() -> VideoFrame:
    return VideoFrame(
        session_id="s1",
        presenter_id="signer1",
        sequence=0,
        timestamp_ms=1000,
        width=640,
        height=480,
        payload_b64=base64.b64encode(b"frame-bytes").decode(),
    )
