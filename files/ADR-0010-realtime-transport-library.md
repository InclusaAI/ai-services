# ADR-0010: Real-Time Transport Library — socket.io

**Status:** Accepted
**Repos affected:** `platform-backend` (`fanout-service`), `realtime-media-backend` (signaling)

## Context
Both `fanout-service` (personalized WebSocket delivery of captions/avatar/translation to clients) and `realtime-media-backend`'s signaling layer needed a WebSocket library choice. Raw `ws` and `socket.io` were the two realistic options, and the two services needed to agree on the same choice rather than deciding independently.

## Decision
Use **`socket.io`** for both `fanout-service` and `realtime-media-backend` signaling.

## Rationale
- `socket.io` provides reconnection handling and room/namespace support out of the box — useful for per-session fan-out grouping in `fanout-service`, and directly relevant given live events are exactly the scenario where a participant's Wi-Fi drops mid-presentation and needs to reconnect cleanly.
- Raw `ws` would require hand-rolling this logic in at least two services independently; not worth the custom plumbing given `socket.io`'s slightly heavier footprint is a reasonable trade-off here.
- Most NestJS real-time examples and community tooling are built around `socket.io`, reducing custom integration work for both services.

## Consequences
- Both services standardize on `socket.io`'s room/namespace model for session-scoped delivery.
- `web-apps` and `mobile-app` client code uses the `socket.io` client SDK, not raw WebSocket APIs, when connecting to `fanout-service`.
- This decision is independent of the LiveKit decision (ADR-0001) — LiveKit handles WebRTC media transport; `socket.io` handles the structured accessibility payload delivery (captions, pose frames, translation text) and signaling messages layered on top.
