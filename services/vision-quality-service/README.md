# vision-quality-service

Assesses the presenter's video (framing, lighting, hand visibility, signing pace)
and publishes quality signals that drive presenter-assist nudges.

## I/O

| | Topic / event key | Payload |
|---|---|---|
| Consumes | `media.session.<id>.video.frame` (pattern, ~15fps — ADR-0007) | `VideoFrame` |
| Publishes | `ai.vision.quality.signal` | `VisionQualitySignal` |
| Publishes | `ai.usage.aggregate` (periodic) | `UsageAggregate` (unit = `quality_signal`) |

Not tied to a per-participant channel, so it is not preference-gated
(`output_channel = None`).

> TODO(throttle): the scaffold emits one signal per frame; production should emit
> on change or at a low cadence. Quality checks are heuristic until a model is
> registered. See `services/asr-service` for the fuller reference.
