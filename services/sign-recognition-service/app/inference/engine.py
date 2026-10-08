"""Sign recognition engine: a pose observation -> closed-set label (+ fingerspelling).

Recognizes against the SAME constrained vocabulary the avatar generates from — the
closed set defined in :mod:`inclusaai_sign_vocab` (symmetric vocabulary, ADR-0002) —
with fingerspelling as the fallback for out-of-vocabulary content.

When a learned model is registered it takes over completely (gated on the ADR-0002
consultation). Until then the engine runs deterministically offline:

* :func:`inclusaai_sign_vocab`-backed **phrase stub** — reduces the extracted
  ``Pose`` to a single integer via :func:`inclusaai_pose_tools.pose_code` and maps
  that into the closed set (placeholder, not a classifier: on real MediaPipe poses
  the reduction collapses toward one label);
* a **real rule-based fingerspelling classifier** — :mod:`app.inference.fingerspelling`
  classifies the dominant handshape against the ASL manual alphabet from landmark
  geometry alone, so the out-of-vocabulary fallback actually recognizes letters
  without any model or dataset.

Temporal aggregation: production classifies *gesture windows*, not individual frames.
:meth:`SignEngine.recognize_window` buffers frames (the pipeline owns the buffer)
and majority-votes the per-frame labels, so a single noisy frame cannot flip a
window's output.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from inclusaai_model_loading import ModelNotAvailable, load_model, measure_latency
from inclusaai_pose_tools import pose_code
from inclusaai_sign_vocab import PHRASE_BY_ID, phrase_ids
from inclusaai_telemetry import get_logger
from pose_format import Pose

from app.config import Settings
from app.inference.fingerspelling import classify_handshape

log = get_logger(__name__)

#: Floor applied to a windowed fingerspelling result's confidence, so a window
#: that mostly saw the classifier's guess still reports it honestly.
_FINGERSPELL_CONFIDENCE_FLOOR = 0.6


@dataclass
class Recognition:
    label: str
    gloss: str | None
    is_fingerspelling: bool
    confidence: float | None = None


@dataclass
class _Vote:
    """One candidate in a window's majority vote."""

    recognition: Recognition
    count: int = 0
    total_confidence: float = 0.0


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

        Offline order of preference: real rule-based fingerspelling (when the
        handshape is recognized) -> closed-set phrase stub.
        """
        if pose is None:
            return []
        with measure_latency(self.settings.service_name, self.settings.model_name or "stub"):
            if self._stub or self._model is None:
                return [self._recognize_offline(pose)]
            # TODO(model-integration): self._model.predict(pose_window)
            raise NotImplementedError("Wire SignEngine.recognize to the registered model.")

    def recognize_window(self, poses: list[Pose]) -> list[Recognition]:
        """Classify a buffered gesture window: per-frame labels, majority vote.

        The winning label is emitted once, with confidence = fraction of frames
        that voted for it (weighted by per-frame handshape confidence for
        fingerspelled letters). An empty window yields no recognitions.
        """
        if not poses:
            return []
        votes: Counter[tuple[str, bool]] = Counter()
        tally: dict[tuple[str, bool], _Vote] = {}
        for pose in poses:
            for rec in self.recognize(pose):
                key = (rec.label, rec.is_fingerspelling)
                vote = tally.setdefault(key, _Vote(recognition=rec))
                vote.count += 1
                vote.total_confidence += rec.confidence or 0.0
                votes[key] += 1

        if not votes:
            return []
        (label, is_fingerspelling), count = votes.most_common(1)[0]
        vote = tally[(label, is_fingerspelling)]
        gloss = vote.recognition.gloss
        # Mean per-frame confidence; fingerspelled letters keep a floor so a
        # window that mostly saw the classifier's guess still reports it honestly.
        confidence = vote.total_confidence / count
        if is_fingerspelling:
            confidence = max(confidence, _FINGERSPELL_CONFIDENCE_FLOOR)
        return [
            Recognition(
                label=label,
                gloss=gloss,
                is_fingerspelling=is_fingerspelling,
                confidence=round(confidence, 4),
            )
        ]

    # ------------------------------------------------------------------ offline
    def _recognize_offline(self, pose: Pose) -> Recognition:
        """Real fingerspelling first, closed-set phrase stub second."""
        shape = classify_handshape(pose)
        if shape is not None:
            return Recognition(
                label=shape.letter,
                gloss=shape.letter.upper(),
                is_fingerspelling=True,
                confidence=shape.confidence,
            )
        return self._recognize_phrase_stub(pose)

    @staticmethod
    def _recognize_phrase_stub(pose: Pose) -> Recognition:
        """Deterministic offline classifier into the closed vocabulary.

        Reduces the pose to a stable code and maps it to a label in the SAME closed
        set the avatar generates from (``inclusaai_sign_vocab.phrase_ids()``).
        Stand-in for the model.
        """
        code = pose_code(pose)
        ids = phrase_ids()
        phrase = PHRASE_BY_ID[ids[code % len(ids)]]
        return Recognition(label=phrase.id, gloss=phrase.gloss, is_fingerspelling=False)
