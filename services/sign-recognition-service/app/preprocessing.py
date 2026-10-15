"""Frame preprocessing: transported video frame -> encoded image bytes.

The transport carries the frame base64-encoded (see ``VideoFrame.payload_b64``);
this undoes only that transport layer, returning the raw *encoded* image bytes
(e.g. JPEG). Decoding those bytes to a pixel array (``cv2.imdecode``) happens in
:mod:`app.detection`, co-located with the other heavy, guarded perception deps
(opencv + mediapipe) so this module stays import-safe on the offline-boot path.
"""

from __future__ import annotations

import base64

from inclusaai_contracts.events import VideoFrame


def decode_frame(frame: VideoFrame) -> bytes:
    """Undo the base64 transport, returning the raw encoded image bytes.

    Raises ``ValueError`` (``binascii.Error`` subclasses it) on malformed base64
    rather than letting it escape as a 500 — a corrupt payload is bad client
    input, and the caller decides how to surface it (the REST layer returns 422).
    """
    try:
        return base64.b64decode(frame.payload_b64)
    # binascii.Error ("Incorrect padding", invalid length) subclasses ValueError.
    except ValueError as exc:
        raise ValueError(f"payload_b64 is not valid base64: {exc}") from exc
