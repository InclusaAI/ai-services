"""sign-recognition pipeline: ``media.*.video.frame`` -> ``ai.sign.recognition.result``.

Frames are buffered into per-session **gesture windows** (``gesture_window_frames``
frames, ~1s at the ADR-0007 15fps sampling rate) and classified window-at-a-time via
:meth:`SignEngine.recognize_window` — production recognizes a *gesture*, not each
individual frame, and a single noisy frame cannot flip a window's output.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from inclusaai_ai_core import BaseInferencePipeline
from inclusaai_contracts.events import AccessibilityChannel, VideoFrame
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
    # Recognition is foundational — it feeds BOTH captions (gloss -> captions for
    # hearing participants) and translation (-> tts), so a single-channel gate would
    # switch the work off as soon as either one channel was disabled. Gate on "is any
    # of these needed": run while anyone in the session needs captions or translation,
    # skip only when nobody does (the TODO(gating) this closes).
    output_channels = (
        AccessibilityChannel.CAPTIONS,
        AccessibilityChannel.TRANSLATION,
    )
    usage_unit = "sign_segment"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings, subscription=VIDEO_FRAME_SUBSCRIPTION)
        self.sign_language = settings.sign_language
        self.engine = SignEngine(settings)
        # One rolling gesture window per session (frames interleave across sessions).
        self._windows: dict[str, _GestureWindow] = {}

    async def on_start(self) -> None:
        self.engine.load()

    def _evict_lru(self) -> None:
        """Bound the per-session gesture-window cache.

        Frames arrive for every session the broker fans out, and a session that ends
        (or stops signing) mid-window leaves a partial buffer behind. Without a bound
        that grows for the process lifetime. ``handle`` re-inserts a window on every
        frame, so insertion order is least-recently-seen and the front is the one to
        drop.
        """
        while len(self._windows) > self.settings.max_gesture_sessions:
            del self._windows[next(iter(self._windows))]

    async def handle(self, event_key: str, model: BaseModel) -> None:
        if not isinstance(model, VideoFrame):
            return
        if not self.should_generate(model.session_id):
            # Nobody in this session needs captions or translation: drop any partial
            # window so a re-enabled session never resumes on stale poses.
            self._windows.pop(model.session_id, None)
            return
        pose = extract_landmarks(decode_frame(model))
        if pose is None:
            return  # nothing to see in this frame — no phantom emissions

        # pop/re-insert keeps the dict in least-recently-seen order (see _evict_lru).
        window = self._windows.pop(model.session_id, None) or _GestureWindow(
            capacity=self.settings.gesture_window_frames
        )
        window.add(pose, model.timestamp_ms)
        self._windows[model.session_id] = window
        self._evict_lru()
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
