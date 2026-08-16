"""Frame preprocessing: transported video frame -> decoded image bytes."""

from __future__ import annotations

import base64

from inclusaai_contracts.events import VideoFrame


def decode_frame(frame: VideoFrame) -> bytes:
    """Decode the transported frame payload to raw image bytes.

    TODO(codec): decode JPEG/whatever ``encoding`` the media backend uses into an
    array (e.g. via opencv) before landmark extraction.
    """
    return base64.b64decode(frame.payload_b64)
