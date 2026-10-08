"""sign-recognition pipeline: ``media.*.video.frame`` -> ``ai.sign.recognition.result``.

Frames are buffered into per-session **gesture windows** (``gesture_window_frames``
frames, ~1s at the ADR-0007 15fps sampling rate) and classified window-at-a-time via
:meth:`SignEngine.recognize_window` — production recognizes a *gesture*, not each
individual frame, and a single noisy frame cannot flip a window's output.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from inclusaai_ai_core import BaseInferencePipeline
from inclusaai_contracts.events import VideoFrame
from inclusaai_kafka_clients.topics import VIDEO_FRAME_SUBSCRIPTION
from pose_format import Pose
from pydantic import BaseModel

from app.config import Settings
from app.detection import extract_landmarks
from app.inference.engine import SignEngine
from app.postprocessing import to_result
from app.preprocessing import decode_frame


@dataclass
class _GestureWindow:
    """A rolling buffer of poses for one session, classified when full."""

    capacity: int
    poses: list[Pose] = field(default_factory=list)
    start_ms: int | None = None
    end_ms: int | None = None

    def add(self, pose: Pose, timestamp_ms: int) -> None:
        if self.start_ms is None:
            self.start_ms = timestamp_ms
        self.end_ms = timestamp_ms
        self.poses.append(pose)

    @property
    def is_full(self) -> bool:
        return len(self.poses) >= self.capacity


class SignPipeline(BaseInferencePipeline):
    # Recognizing a signer's input is foundational (feeds captions/translation for
    # hearing participants), so it is not gated on a single output channel.
    # TODO(gating): skip when no participant in the session is signing.
    output_channel = None
    usage_unit = "sign_segment"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings, subscription=VIDEO_FRAME_SUBSCRIPTION)
        self.sign_language = settings.sign_language
        self.engine = SignEngine(settings)
        # One rolling gesture window per session (frames interleave across sessions).
        self._windows: dict[str, _GestureWindow] = {}

    async def on_start(self) -> None:
        self.engine.load()

    async def handle(self, event_key: str, model: BaseModel) -> None:
        if not isinstance(model, VideoFrame):
            return
        pose = extract_landmarks(decode_frame(model))
        if pose is None:
            return  # nothing to see in this frame — no phantom emissions

        window = self._windows.setdefault(
            model.session_id, _GestureWindow(capacity=self.settings.gesture_window_frames)
        )
        window.add(pose, model.timestamp_ms)
        if not window.is_full:
            return  # keep buffering until the gesture window is complete

        del self._windows[model.session_id]
        recognitions = self.engine.recognize_window(window.poses)
        for recognition in recognitions:
            result = to_result(
                model,
                recognition,
                self.sign_language,
                start_ms=window.start_ms or model.timestamp_ms,
                end_ms=window.end_ms or model.timestamp_ms,
            )
            # key by session so a session's results stay ordered on one partition.
            await self.publish("ai.sign.recognition.result", result, key=model.session_id)
