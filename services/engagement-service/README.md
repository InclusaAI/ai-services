# engagement-service

Aggregates session-level audience signals (participants joining/leaving, reactions)
over a fixed time window and publishes a periodic engagement aggregate that drives
presenter dashboards and adaptive-pacing hints.

## I/O

| | Topic / event key | Payload |
|---|---|---|
| Consumes | `media.session.<id>.participant.{joined,left}` (pattern) | `ParticipantEvent` |
| Publishes | `ai.engagement.signal.aggregate` (every `window_seconds`) | `EngagementSignalAggregate` |
| Publishes | `ai.usage.aggregate` (periodic) | `UsageAggregate` (unit = `engagement_window`) |

Unlike every other service this one does **not** publish per input event — it
accumulates and flushes on a window (`window_seconds`, default 60) from a background
task started in `on_start` and drained in `on_stop`. It is not preference-gated
(`output_channel = None`) and has no ML model — aggregation is pure Python.

## Privacy (ai-services-IMPLEMENTATION.md §2)

`EngagementSignalAggregate` **structurally** excludes any per-individual identifier —
no `participant_id`/`user_id`, only session-level counts over a window. Participant
ids are used transiently inside [aggregation.py](app/aggregation.py) to compute
`participant_count` and are never emitted. A test asserts the contract carries no such
field — keep it that way; adding one is a contract violation, not just a policy one.
