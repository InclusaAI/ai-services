"""sign-recognition-service configuration."""

from __future__ import annotations

from inclusaai_ai_core import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "sign-recognition-service"
    kafka_consumer_group: str = "sign-recognition-service"

    # Registered recognition model (None -> offline stub).
    model_name: str | None = "sign-recognition-asl"

    # Video sampling rate the upstream media backend emits at (ADR-0007 starting point).
    video_sample_fps: int = 15
    # Frames buffered per gesture before classification (~1s at 15fps). The recognizer
    # votes over a window instead of emitting per-frame, so one noisy frame can't flip
    # a result.
    gesture_window_frames: int = 15
    # Upper bound on sessions buffered at once. The broker fans out every session's
    # frames to every replica, so a session that stops mid-window would otherwise pin
    # its partial buffer for the process lifetime; least-recently-seen windows are
    # evicted past this count.
    max_gesture_sessions: int = 256
    # ASL only for MVP; the recognized vocabulary is the SAME closed set the avatar
    # generates from (symmetric vocabulary, ADR-0002).
    sign_language: str = "ASL"


settings = Settings()
