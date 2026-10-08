# sign-recognition-service

Recognizes a signer's ASL from the video stream and publishes recognition results
that feed captions/translation for hearing participants.

Recognition is **in scope for the MVP** as a *symmetric, closed-set* problem: the
recognized vocabulary is the same constrained set (~150–300 phrases) the
avatar-pose service generates from, plus fingerspelling for out-of-vocabulary
content (ADR-0002, revised). Both services import that set from
[`inclusaai_sign_vocab`](../../shared/sign_vocab/README.md) — the single source of
truth — so the recognizer only ever emits labels the avatar can also produce.

## I/O

| | Topic / event key | Payload |
|---|---|---|
| Consumes | `media.session.<id>.video.frame` (pattern, ~15fps — ADR-0007) | `VideoFrame` |
| Publishes | `ai.sign.recognition.result` | `SignRecognitionResult` |
| Publishes | `ai.usage.aggregate` (periodic) | `UsageAggregate` (unit = `sign_segment`) |

## Layout

```
app/
  config.py          # Settings: model, video_sample_fps, gesture_window_frames, sign_language
  preprocessing.py   # undo base64 transport -> encoded image bytes
  detection.py       # MediaPipe Holistic -> 51-pt skeleton Pose (guarded; degrades to a fake pose)
  inference/
    engine.py        # SignEngine: skeleton Pose -> closed-set label (+ fingerspelling)
    fingerspelling.py# rule-based ASL handshape classifier over the 51-pt skeleton (offline, model-free)
  postprocessing.py  # build the SignRecognitionResult contract payload
  pipeline.py        # video.frame -> sign.recognition.result (buffers per-session gesture windows)
```

### Representation & perception

The internal pose representation is [`pose-format`](https://github.com/sign-language-processing/pose)'s
`Pose`, bridged to the 51-point skeleton and the wire contract by
[`inclusaai_pose_tools`](../../shared/pose_tools/README.md) — the same container
`avatar-pose-service` generates into (matched-pair symmetry, now at the representation level too).

`detection.py` runs **real MediaPipe Holistic** (via pose-format's `load_holistic`), subsetting the
543-point holistic output to our 51-point skeleton. MediaPipe is **guarded-imported and not installed
by default**: MediaPipe Holistic pins `protobuf<5`, but this monorepo's contracts + OpenTelemetry stack
is on `protobuf>=5` — an unsatisfiable single-environment conflict. So extraction degrades to a
deterministic placeholder pose with a loud `sign.mediapipe_unavailable` log (exactly how `asr-service`
degrades without faster-whisper), and the pipeline stays fully exercisable offline. To run the real
path, install `pose-format[mediapipe]` + `opencv-python-headless` into a `protobuf<5` environment and
set `SIGN_RUN_MEDIAPIPE_TESTS=1`.

Runs **offline** when no model is registered, so the wiring is exercisable without
MLflow/Kafka/GPU:

- **Fingerspelling is real, not stubbed.** `inference/fingerspelling.py` classifies
  the signer's dominant handshape against the ASL manual alphabet from landmark
  geometry alone (per-finger curl + thumb placement) — a bounded, model-free
  fallback for out-of-vocabulary content (ADR-0002). It statically covers
  `a b c d f g i l r u v w y`; motion- and orientation-dependent letters fall
  through to the closed-set phrase stub.
- **Phrases are the deterministic stub** until a learned model is registered — a
  placeholder reduction of the pose to a closed-set label (matched-pair symmetry
  with the avatar's vocabulary), gated on the ADR-0002 consultation.
- **Gestures, not frames.** The pipeline buffers per-session **gesture windows**
  (`gesture_window_frames`, ~1s at 15fps) and majority-votes the per-frame labels,
  so one noisy frame can't flip a result.

See `services/asr-service` for the fuller reference (incl. the optional gRPC servicer
pattern). Real recognition *content* (verified glosses, a learned model) stays gated
on the ADR-0002 consultation.
