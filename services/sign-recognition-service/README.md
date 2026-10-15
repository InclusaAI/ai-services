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
  api/rest.py        # debug REST router: POST /v1/recognize, GET /v1/labels
```

### Debug REST API

Health/readiness/metrics come from `inclusaai_ai_core`; this adds a synchronous,
broker-free view of the engine. Interactive docs are at `/docs`, and every request
body is **pre-filled with a working example** so "Try it out" just works.

| | Route | Purpose |
|---|---|---|
| `POST` | `/v1/recognize` | One `VideoFrame` (base64 JPEG) -> `[SignRecognitionResult]` |
| `GET` | `/v1/labels` | The closed label set + fingerspelling alphabet + window config |

Try it with curl (the payload is a real 1x1 JPEG):

```bash
curl -sS -X POST http://localhost:8080/v1/recognize \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"demo","presenter_id":"p1","sequence":0,"timestamp_ms":0,
       "width":1,"height":1,"fps":15,
       "payload_b64":"/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAABAAAAAAAAAAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AKp//2Q=="}'
# -> [{"session_id":"demo-session","signer_id":"presenter-1","segment_id":"sign_...",
#      "label":"number_10","gloss":"TEN","is_fingerspelling":false,
#      "start_ms":0,"end_ms":0,"confidence":null,"sign_language":"ASL"}]
```

(`label` is a **placeholder** — with MediaPipe uninstalled, extraction degrades to a
deterministic fake pose, so the label is arbitrary. The `sign_<random>` segment id is
generated per call. This is the plumbing under test, not recognition quality.)

```bash
curl -sS http://localhost:8080/v1/labels | jq '{sign_language, phrases: (.phrases|length), fingerspelling}'
# {"sign_language":"ASL","phrases":56,"fingerspelling":["a","b","c", ...]}  (26 letters)
```

**Status codes** — bad input is always a 4xx, never a 500:

| Code | Meaning |
|---|---|
| `200` | Zero or one result. `[]` means nothing to recognize (empty payload -> no pose). |
| `422` | Missing/invalid fields, **or** `payload_b64` is not valid base64 (the message says so). |

This is the **single-frame** path: the Kafka pipeline buffers a gesture window and
majority-votes before publishing, so a noisy frame here can flip a label the pipeline
would have smoothed out. Use it for smoke tests, not for parity checking.

### Preference gating

Recognition feeds **two** channels — `CAPTIONS` (gloss -> captions) and `TRANSLATION`
(gloss -> translation -> tts) — so it is gated on "is *any* of these needed"
(`output_channels`), not on a single channel. A single-channel check would switch the
work off as soon as either channel was disabled, dropping output somebody still
needed. Gating is fail-open: until preferences for a session arrive, recognition runs.

Per-session gesture windows are held in an LRU-bounded cache
(`max_gesture_sessions`, default 256). The broker fans every session's frames to every
replica, so without a bound a session that stops mid-window would pin its partial
buffer for the process lifetime. A gated-off session's partial window is dropped rather
than resumed.

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
