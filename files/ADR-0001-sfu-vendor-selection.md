# ADR-0001: SFU Vendor Selection — LiveKit

**Status:** Accepted
**Repos affected:** `realtime-media-backend`, `web-apps`, `mobile-app`

## Context
`realtime-media-backend` needs a WebRTC SFU for audio/video ingest, signaling, and relay. The two realistic candidates were **LiveKit** (managed or self-hosted) and **mediasoup** (self-hosted only).

## Decision
Use **LiveKit** for MVP and the foreseeable roadmap.

## Rationale
- Self-hosting mediasoup means the team also owns SFU infrastructure, TURN server management, and scaling logic on top of everything else on the roadmap — real cost for a small team pre-launch.
- LiveKit reaches a working demo in weeks rather than requiring infrastructure build-out first.
- LiveKit has built-in recording hooks, which directly feeds ADR-0006 (recording-service).
- The `SfuAdapter` interface in `realtime-media-backend` keeps this swappable — LiveKit is not a one-way door. Migrate to self-hosted mediasoup later only if LiveKit Cloud cost becomes a genuine problem at scale.

## Consequences
- `web-apps` and `mobile-app` standardize on the LiveKit client SDK.
- Video frame sampling for AI consumption (ADR-0007) is designed against LiveKit's media pipeline.
- Revisit if LiveKit's pricing model doesn't hold up under real concurrent-session load — track cost per session as a metric from first production use.
