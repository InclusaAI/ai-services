# avatar-pose-service

Generates a signing avatar's skeletal pose frames from transcript text, using a
constrained-vocabulary phrase library (ADR-0002).

## I/O

| | Topic / event key | Payload |
|---|---|---|
| Consumes | `ai.transcript.segment` | `TranscriptSegment` |
| Consumes | `accessibility.preference.updated` | handled by the base pipeline (drives gating) |
| Publishes | `ai.avatar.pose.frame` | `AvatarPoseFrame` (one per animation frame) |
| Publishes | `ai.usage.aggregate` (periodic) | `UsageAggregate` (unit = `avatar_pose_frame`) |

**Preference-gated** on the `avatar` channel (`output_channel = AVATAR`).

> `AvatarPoseFrame` is the highest-frequency, most bandwidth-sensitive schema in
> the platform — version it carefully and load-test the fan-out path
> (IMPLEMENTATION §5).

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
