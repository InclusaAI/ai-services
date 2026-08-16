# ADR-0007: Video Frame Sampling Rate for CV Pipeline — 15fps Starting Point

**Status:** Accepted (starting parameter, expected to be tuned with real data)
**Repos affected:** `realtime-media-backend`, `ai-services`

## Context
`realtime-media-backend` samples video frames from presenter camera input and publishes them to Kafka for `ai-services`' sign-recognition and vision-quality services to consume. Full 30/60fps publishing was considered but flagged as unnecessary Kafka throughput cost without a clear accuracy requirement driving it.

## Decision
Start video frame sampling at **15fps** for CV/sign-recognition input.

## Rationale
- MediaPipe-based sign language recognition pipelines are commonly built and evaluated around ~15fps in existing research and tooling; this is a reasonable, well-precedented starting point rather than an arbitrary guess.
- Full framerate publishing floods Kafka with data the recognition model doesn't need, at real infrastructure cost, without evidence it improves accuracy.

## Consequences
- This is explicitly a **starting point, not a fixed constraint**. `ai-services`' sign-recognition team should be tracking recognition accuracy against sampling rate as a real metric once evaluation data exists, and this ADR should be revisited (superseded, not silently overridden) if accuracy data justifies a higher rate.
- `realtime-media-backend` and `ai-services` need to co-own this parameter going forward — it shouldn't be changed unilaterally by either side without the other being aware, since it affects both Kafka throughput planning and model training/evaluation assumptions.
