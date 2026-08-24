"""Sign recognition engine: a pose observation -> closed-set label (+ fingerspelling).

Recognizes against the SAME constrained vocabulary the avatar generates from — the
closed set defined in :mod:`inclusaai_sign_vocab` (symmetric vocabulary, ADR-0002) —
with fingerspelling as the fallback for out-of-vocabulary content. Runs a deterministic
stub until a learned model is registered.

The stub reduces the extracted ``Pose`` to a single integer via
:func:`inclusaai_pose_tools.pose_code` and maps that into the closed set. It is a
placeholder, not a classifier (on real MediaPipe poses the reduction collapses toward
one label); real recognition arrives with the learned model, gated on ADR-0002.
"""

from __future__ import annotations

from dataclasses import dataclass

from inclusaai_model_loading import ModelNotAvailable, load_model, measure_latency
from inclusaai_pose_tools import pose_code
from inclusaai_sign_vocab import FINGERSPELL_ALPHABET, PHRASE_BY_ID, phrase_ids
from inclusaai_telemetry import get_logger
from pose_format import Pose

from app.config import Settings

log = get_logger(__name__)

# Stub-classifier tuning: 1-in-N pose codes route to the fingerspelling fallback, so
# both the closed-set and out-of-vocabulary paths are exercised offline. The learned
# model replaces this wholesale (ADR-0002 consultation gate).
_FINGERSPELL_EVERY = 7


@dataclass
class Recognition:
    label: str
    gloss: str | None
    is_fingerspelling: bool
    confidence: float | None = None


class SignEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._model: object | None = None
        self._stub = True

    def load(self) -> None:
        if not self.settings.model_name:
            log.warning("sign.stub_mode", reason="no model_name configured")
            return
        try:
            self._model = load_model(
                self.settings.model_name,
                stage=self.settings.model_stage,
                version=self.settings.model_version,
                tracking_uri=self.settings.mlflow_tracking_uri,
            )
            self._stub = False
        except ModelNotAvailable as exc:
            log.error("sign.model_unavailable", error=str(exc))

    def recognize(self, pose: Pose | None) -> list[Recognition]:
        """Classify one pose observation. Returns [] when there's nothing to classify.

        TODO(model): production buffers frames into temporal gesture windows before
        classifying, rather than emitting per frame.
        """
        if pose is None:
            return []
        with measure_latency(self.settings.service_name, self.settings.model_name or "stub"):
            if self._stub or self._model is None:
                return [self._recognize_stub(pose)]
            # TODO(model-integration): self._model.predict(pose_window)
            raise NotImplementedError("Wire SignEngine.recognize to the registered model.")

    @staticmethod
    def _recognize_stub(pose: Pose) -> Recognition:
        """Deterministic offline classifier into the closed vocabulary.

        Reduces the pose to a stable code and maps it to a label in the SAME closed set
        the avatar generates from (``inclusaai_sign_vocab.phrase_ids()``), reserving a
        slice of the code space for the fingerspelling fallback. Stand-in for the model.
        """
        code = pose_code(pose)
        if code % _FINGERSPELL_EVERY == 0:
            letter = FINGERSPELL_ALPHABET[(code // _FINGERSPELL_EVERY) % len(FINGERSPELL_ALPHABET)]
            return Recognition(label=letter, gloss=letter.upper(), is_fingerspelling=True)
        ids = phrase_ids()
        phrase = PHRASE_BY_ID[ids[code % len(ids)]]
        return Recognition(label=phrase.id, gloss=phrase.gloss, is_fingerspelling=False)
