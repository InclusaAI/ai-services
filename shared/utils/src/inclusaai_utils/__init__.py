"""Small shared helpers used across services."""

from __future__ import annotations

import time
import uuid


def now_ms() -> int:
    """Current wall-clock time in milliseconds since the epoch."""
    return int(time.time() * 1000)


def new_id(prefix: str = "") -> str:
    """A short unique id, optionally prefixed (e.g. ``seg_...``)."""
    token = uuid.uuid4().hex[:16]
    return f"{prefix}_{token}" if prefix else token


__all__ = ["now_ms", "new_id"]
