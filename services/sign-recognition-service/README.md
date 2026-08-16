# sign-recognition-service

Recognizes a signer's ASL from the video stream and publishes recognition results
that feed captions/translation for hearing participants.

Recognition is **in scope for the MVP** as a *symmetric, closed-set* problem: the
recognized vocabulary is the same constrained set (~150–300 phrases) the
avatar-pose service generates from, plus fingerspelling for out-of-vocabulary
content (ADR-0002, revised).

## I/O

| | Topic / event key | Payload |
|---|---|---|
| Consumes | `media.session.<id>.video.frame` (pattern, ~15fps — ADR-0007) | `VideoFrame` |
| Publishes | `ai.sign.recognition.result` | `SignRecognitionResult` |
| Publishes | `ai.usage.aggregate` (periodic) | `UsageAggregate` (unit = `sign_segment`) |

## Layout

```
app/
  config.py          # Settings: model, video_sample_fps, sign_language
  preprocessing.py   # decode transported frame -> image bytes
  detection.py       # MediaPipe landmark extraction (stub)
  inference/engine.py# SignEngine: landmark window -> closed-set label (+ fingerspelling); stub until a model is registered
  postprocessing.py  # build the SignRecognitionResult contract payload
  pipeline.py        # video.frame -> sign.recognition.result
```

Runs a deterministic **stub** engine when no model is registered, so the wiring is
exercisable offline. See `services/asr-service` for the fuller reference (incl. the
optional gRPC servicer pattern).
