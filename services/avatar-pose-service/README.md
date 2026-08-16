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
against (symmetric vocabulary). A learned text→pose model is an optional future
replacement for the lookup. See `services/asr-service` for the fuller reference.
