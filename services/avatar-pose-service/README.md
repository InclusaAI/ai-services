# avatar-pose-service

Generates a signing avatar's skeletal pose frames from transcript text, using a
constrained-vocabulary phrase library (ADR-0002).

## I/O

| | Topic / event key | Payload |
|---|---|---|
| Consumes | `ai.transcript.segment` | `TranscriptSegment` |
| Consumes | `ai.translation.result` | `TranslationResult` — the Deaf-presenter leg |
| Consumes | `accessibility.preference.updated` | handled by the base pipeline (drives gating) |
| Publishes | `ai.avatar.pose.frame` | `AvatarPoseFrame` (one per animation frame) |
| Publishes | `ai.usage.aggregate` (periodic) | `UsageAggregate` (unit = `avatar_pose_frame`) |

**Preference-gated** on the `avatar` channel (`output_channel = AVATAR`).

### Two inputs, one direction of travel

Both text inputs render through the same constrained vocabulary, and both are needed
for the product to actually be bidirectional:

* **`ai.transcript.segment`** — speech in, avatar signs it. Hearing speaker → Deaf audience.
* **`ai.translation.result`** — the **Deaf-presenter leg**, and the reason this service
  exists: a Deaf presenter signs, sign-recognition recognizes the gloss, translation
  renders it, and the avatar signs the translated text back out so hearing participants
  can *see* what was said. Without this input the reverse direction doesn't exist and
  the platform is captions-only in reverse.

On the translation leg the avatar signs **`translated_text`** (the target language) —
never `source_text`, which is the sign gloss. `TranslationResult` carries no segment
timing, so those frames anchor on arrival time (`now_ms()`) rather than the source
segment's start; the contract has no segment id or language field to carry that, so a
client distinguishing concurrent phrases groups on `timestamp_ms`/`phrase_id`. Adding
segment timing to the contract is the clean fix and is deliberately left as a contract
change rather than guessed at here.

> `AvatarPoseFrame` is the highest-frequency, most bandwidth-sensitive schema in
> the platform — version it carefully and load-test the fan-out path
> (IMPLEMENTATION §5).

## Debug REST API

Health/readiness/metrics come from `inclusaai_ai_core`; this adds a synchronous,
broker-free view of the generator. Interactive docs are at `/docs`, and the request
body is **pre-filled with a working example** so "Try it out" just works.

| | Route | Purpose |
|---|---|---|
| `POST` | `/v1/pose` | `{"text": ..., "session_id": ..., "start_ms": ...}` -> `[AvatarPoseFrame]` |
| `GET` | `/v1/vocabulary` | The closed phrase set + fingerspelling alphabet |

```bash
curl -sS -X POST http://localhost:8080/v1/pose \
  -H 'Content-Type: application/json' \
  -d '{"text":"hello there","session_id":"demo","start_ms":0}'
# -> [{"session_id":"demo","phrase_id":"hello","frame_index":0,
#      "timestamp_ms":0,"fps":30,
#      "keypoints":[{"x":0.379,"y":0.613,"z":0.052,"visibility":1.0}, ...51 more]}, ...8 frames]
```

```bash
curl -sS http://localhost:8080/v1/vocabulary | jq '{phrase_count, first: .phrases[0]}'
# {"phrase_count":56,"first":{"id":"hello","gloss":"HELLO","category":"greeting"}}
```

Keypoint coordinates are a deterministic **placeholder** animation (stable per phrase
id, see `app/vocabulary.py`) — realistic in shape, not real motion capture.

**Status codes** — `200` returns the frame sequence (`phrase_id` null when the text was
out-of-vocabulary and got fingerspelled); `422` if the body is missing `text`.

Out-of-vocabulary and empty input still return frames (fingerspelled / neutral
resting), so you always get something inspectable back.

The pose sequence produced here is identical to the pipeline's; only the driver differs.

The vocabulary is the **same closed set** the sign-recognition service classifies
against — both import [`inclusaai_sign_vocab`](../../shared/sign_vocab/README.md), the
single source of truth for the symmetric vocabulary (ADR-0002), so the two can't drift.
`app/vocabulary.py` turns a matched phrase into a deterministic full-skeleton pose
sequence — a [`pose-format`](https://github.com/sign-language-processing/pose) `Pose` built via
[`inclusaai_pose_tools`](../../shared/pose_tools/README.md), the same representation
`sign-recognition-service` extracts into (matched-pair symmetry now at the representation level too).
It is a placeholder for real motion data (see that module) and fingerspells out-of-vocabulary text.
A learned text→pose model is an optional future replacement for this lookup. See
`services/asr-service` for the fuller reference.
