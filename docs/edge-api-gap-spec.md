# Edge API Gap Spec (Draft)

**Status:** Draft for alignment between frontend (`@inclusaai/api-client`) and `ai-services`  
**Date:** 2026-11-11  
**Source gap analysis:** Frontend integration gaps for staging services (`ai-services-5fo4.onrender.com`, `avatar-pose-service.onrender.com`)

## 1. Purpose & scope

This document specifies the **client-facing HTTP/WS API gaps** requested by the frontend and maps them to the current `ai-services` repo (Kafka-first inference microservices, shared contracts in `shared/contracts`). It is intended to:

- unblock frontend integration with stable request/response/message contracts,
- clarify what can be implemented as thin facades over existing pipelines vs. net-new work,
- identify contract decisions that must be settled before implementation (especially pose streaming).

**Out of scope:** replacing internal Kafka/event architecture, model training/research, infra/deployment topology details beyond noting Render staging targets.

## 2. Current repo baseline (relevant)

| Area | Current state in repo | Gap vs requested edge API |
|---|---|---|
| ASR HTTP | `POST /v1/transcribe` (JSON `AudioChunk` → `TranscriptSegment[]`), `POST /v1/transcribe/file`, `GET /v1/formats` in `services/asr-service/app/api/rest.py` | Missing/renamed `GET /v1/models`; no streaming WS |
| Avatar pose | Kafka pipeline `ai.transcript.segment` → `ai.avatar.pose.frame` (`AvatarPoseFrame`: `session_id`, `phrase_id`, `frame_index`, `timestamp_ms`, `fps`, `keypoints[{x,y,z,visibility}]`); vocab/sign assets in `shared/sign_vocab`, `services/avatar-pose-service/app/vocabulary.py`; no service REST routes | Missing `POST /v1/pose`, `GET /v1/vocabulary`, no pose WS stream |
| Translation | Kafka pipeline `ai.transcript.segment` → `ai.translation.result` (`TranslationResult`), preference-gated | Missing `POST /v1/translate` HTTP facade |
| Gloss/text-to-sign tokens | Vocabulary matching + fingerspelling logic exists for pose generation; no gloss contract/endpoint | Missing `POST /v1/gloss` (gap text also mentions `/v1/glosa`) |
| Streaming | No `WebSocket` endpoints in services; `TranscriptSegment` has `is_final` but no partial-stream protocol | Missing ASR and pose WS streams |
| Pose protocol docs | `pose-protocol-proposal.md`, `pose-protocol-response.md` draft landmark-vs-bone, clip/cadence/confidence/gesture-topic decisions | Not finalized; streaming schema must not be locked prematurely |

## 3. Cross-cutting decisions (must agree)

1. **Serving/ownership:** Does `ai-services` implement public edge endpoints directly (per-service or shared gateway module), or expose only internal contracts for another gateway/BFF? This spec assumes **edge facades may live in this repo** for staging parity, but calls out where a gateway is preferable.
2. **Canonical contracts:** Edge DTOs should map cleanly to `shared/contracts` events/models; where they differ for frontend ergonomics, define explicit adapters and keep wire contracts versioned.
3. **Naming compatibility:** Support requested paths/names for frontend now (`/v1/models`, `/v1/gloss`) and add aliases only where necessary (`/v1/formats`, `/v1/glosa`).
4. **Auth/rate limits/session ownership:** Not defined in repo; staging endpoints must specify auth mechanism (e.g. bearer/API key), CORS/origin policy, and per-session authorization.
5. **Error envelope (recommended, all HTTP):**
   ```json
   {
     "error": {
       "code": "invalid_argument",
       "message": "Human-readable detail",
       "details": {}
     }
   }
   ```
   Suggested codes: `invalid_argument`, `unsupported_media_type`, `unsupported_language`, `unsupported_sign_language`, `session_not_found`, `rate_limited`, `unavailable`, `internal`.
6. **Timebase:** `*_ms` fields are Unix epoch milliseconds unless stated; WS streams must document whether timestamps are source/ingest-relative or absolute.

## 4. HTTP endpoint specs

### 4.1 `GET /v1/models` (ASR) — parity gap

**Status:** Missing in repo (ASR currently has `GET /v1/formats`).  
**Goal:** Match frontend `@inclusaai/api-client` expectations.

**Request:** none.

**Proposed response (to confirm with frontend):**
```json
{
  "models": [
    {
      "id": "whisper-1",
      "name": "Whisper",
      "task": "transcribe",
      "languages": ["en"],
      "streaming": false,
      "default": true
    }
  ]
}
```

**Implementation notes:** derive from ASR engine/config/model registry metadata; if unavailable in stub mode, return deterministic defaults. Consider keeping `GET /v1/formats` as an alias/additional endpoint for capability discovery.

**Errors:** `503 unavailable` if model metadata cannot be produced (or return stub capabilities when running offline, per service behavior).

---

### 4.2 `POST /v1/transcribe` (ASR) — existing, verify parity

**Status:** Implemented.  
**Current contract:** JSON body = `AudioChunk` (`session_id`, `speaker_id`, `sequence`, `timestamp_ms`, `sample_rate`, `encoding`, `payload_b64`) → `TranscriptSegment[]`.

**Parity checks with frontend:**
- Field names/types match exactly (`payload_b64` vs `audio`, `timestamp_ms` naming, required vs optional fields).
- Response shape matches (`segment_id`, `text`, `start_ms`, `end_ms`, `language`, `is_final`, `confidence`).
- Supported encodings/sample rates and chunk duration expectations.

**Recommendation:** keep current contract canonical if frontend already integrates to it; otherwise add an adapter endpoint/versioned payload and document mapping to `AudioChunk`.

---

### 4.3 `POST /v1/transcribe/file` (ASR) — existing

**Status:** Implemented (multipart upload `file`, optional `session_id`, `speaker_id`).  
**Recommendation:** confirm accepted MIME types/size limits and response parity; document `GET /v1/formats`/supported encodings.

---

### 4.4 `GET /v1/vocabulary` (Avatar Pose) — missing

**Status:** Missing HTTP route; vocabulary data exists in shared/service code.

**Request:** optional query params (proposed): `signLanguage=ase|asl` (default MVP: ASL/ASE as agreed), `includeFingerspelling=true|false`.

**Proposed response:**
```json
{
  "signLanguage": "ase",
  "vocabulary": [
    {
      "id": "HELLO",
      "label": "Hello",
      "type": "phrase",
      "aliases": ["hi"]
    }
  ],
  "fingerspelling": {
    "supported": true,
    "alphabet": ["A", "B", "C"]
  },
  "renderable": true
}
```

**Implementation notes:** expose the closed-set renderable vocabulary (ADR-0002 aligned) and explicitly indicate fingerspelling fallback for OOV terms. Exact fields should reflect `shared/sign_vocab` structures.

**Errors:** `400 unsupported_sign_language`.

---

### 4.5 `POST /v1/pose` (Avatar Pose) — missing

**Status:** Missing HTTP route; generation logic exists (`TranscriptSegment`/text → pose frames via vocab/fingerspelling pipeline) and emits `AvatarPoseFrame` events internally.

**Request (from gap, to confirm):**
```json
{
  "text": "Hello everyone",
  "session_id": "session-123",
  "start_ms": 0
}
```

**Proposed response (MVP, aligned to current internal `AvatarPoseFrame` semantics):**
```json
{
  "session_id": "session-123",
  "fps": 30,
  "frames": [
    {
      "phrase_id": "HELLO",
      "frame_index": 0,
      "timestamp_ms": 0,
      "keypoints": [
        { "x": 0.1, "y": 0.2, "z": 0.0, "visibility": 1.0 }
      ]
    }
  ]
}
```

**Open decisions (must settle with frontend/avatar-engine):**
- `keypoints` (landmarks, current repo) vs bone-rotation `bones` format expected by renderer.
- Include `version`, `confidence`, and/or gesture frames/channel metadata.
- Clip semantics for multi-phrase text (single concatenated clip vs multiple clips with `frame_index` reset / `phrase_id` boundaries).
- OOV handling: fingerspell, omit, or include fallback markers.

**Implementation notes:** facade can invoke the same generation path used by `AvatarPosePipeline` without requiring Kafka; return bounded clips (phrase-driven, not continuous mocap).

**Errors:** `400 invalid_argument`, `422 unsupported content` (if needed), `503 unavailable`.

---

### 4.6 `POST /v1/translate` (Translation) — missing (gap 3.2)

**Status:** Missing HTTP route; `translation-service` pipeline/model logic exists (`ai.transcript.segment` → `ai.translation.result`).

**Request:**
```json
{
  "text": "Hello everyone",
  "sourceLanguage": "en",
  "targetLanguage": "es"
}
```

**Response:**
```json
{
  "translatedText": "Hola a todos",
  "detectedSourceLanguage": "en"
}
```

**Mapping to internal contract:** `TranslationResult { session_id, segment_id, source_language, target_language, source_text, translated_text }` (HTTP facade can be stateless/ephemeral `session_id`/`segment_id`).

**Open decisions:**
- Allow `sourceLanguage: "auto"` / omitted for detection? If so, specify detection behavior and confidence (optional field).
- Supported language pairs/models, max text length, normalization/casing, and whether translation is synchronous-only in edge API.
- Behavior when translation service/model is in stub/offline mode.

**Errors:** `400 invalid_argument`, `400 unsupported_language` (or `422`), `503 unavailable`.

---

### 4.7 `POST /v1/gloss` (Text-to-gloss) — missing (gap 3.3)

**Status:** Missing HTTP route; gap text mentions `/v1/glosa` but proposed contract uses `/v1/gloss`. Related vocab/fingerspelling logic exists but no gloss output contract.

**Request (proposed):**
```json
{
  "text": "I am going to the store",
  "signLanguage": "ase"
}
```

**Response (proposed):**
```json
{
  "glossTokens": ["ME", "GO", "STORE"],
  "expressions": ["neutral"],
  "fingerspelled": [],
  "unmapped": []
}
```
(`fingerspelled`/`unmapped` are recommended additions for transparency; can be omitted if frontend requires exact minimal shape.)

**Open decisions:**
- Gloss convention and tokenization rules per sign language (ASL/ASE scope, non-manual markers/expressions vocabulary).
- Alignment/timing hints for downstream pose streaming (optional future fields).
- OOV strategy: fingerspell tokens, pass-through, or drop with `unmapped`.
- Endpoint alias: serve both `/v1/gloss` and `/v1/glosa` during transition.

**Implementation notes:** MVP can be rule-based/vocab-driven using existing constrained vocabulary and fingerspelling utilities; clearly document fidelity limits vs full linguistic glossing.

**Errors:** `400 invalid_argument`, `400 unsupported_sign_language`, `503 unavailable`.

## 5. WebSocket specs

### 5.1 `wss://.../v1/transcribe/stream` — missing (gap 3.1)

**Goal:** Low-latency streaming ASR with partial hypotheses and final commits.

#### Connection/session
- **URL:** `wss://<ai-service-host>/v1/transcribe/stream` (query/header auth TBD).
- **Client → server control (JSON, text frame), recommended:**
  ```json
  { "type": "start", "session_id": "s1", "sampleRate": 16000, "encoding": "pcm_s16le", "channels": 1, "language": "en" }
  ```
  ```json
  { "type": "end" }
  ```
- **Binary audio frames:** client sends **100ms PCM16 LE mono @ 16kHz** slices by default (`3200 bytes` per 100ms frame). Server may accept negotiated frame sizes but must document limits.

#### Server → client events (JSON text frames)
```json
{ "type": "partial", "text": "Welcome to our", "startMs": 0, "endMs": 1200, "segmentId": "seg-1", "confidence": 0.82 }
```
```json
{ "type": "final", "text": "Welcome to our session", "startMs": 0, "endMs": 1800, "segmentId": "seg-1", "confidence": 0.94, "isFinal": true }
```
```json
{ "type": "error", "code": "invalid_audio_format", "message": "..." }
```
```json
{ "type": "ready", "session_id": "s1" }
```

**Required protocol details to finalize:**
- Whether `start` is mandatory or inferred on first binary frame.
- Timestamp semantics (`startMs/endMs`: stream-relative vs absolute/session clock).
- Partial update semantics (replace vs append; stable `segmentId` rules).
- Commit/finalization triggers (silence/VAD, explicit `end`, max utterance duration).
- Backpressure/rate limits, max buffered audio, heartbeat/ping-pong, idle timeout.
- Ordering and at-most/at-least-once delivery expectations per segment.
- Reconnect/resume: session resumption token or restart-only.

**Mapping to repo:** can reuse ASR decode/inference path and emit `TranscriptSegment`-like payloads; partial hypotheses require engine/pipeline support beyond current chunk-final behavior.

---

### 5.2 `wss://.../v1/pose/stream` — missing (gap 3.4)

**Goal:** Stream 30fps avatar pose frames synchronized to presenter/audio clock without buffering full utterances.

#### Connection/session
- **URL:** `wss://<avatar-pose-host>/v1/pose/stream`.
- **Client → server control (JSON), recommended:**
  ```json
  { "type": "start", "session_id": "s1", "signLanguage": "ase", "fps": 30 }
  ```
  ```json
  { "type": "text", "text": "Hello everyone", "startMs": 0, "utteranceId": "u1" }
  ```
  ```json
  { "type": "gloss", "tokens": ["HELLO", "EVERYONE"], "startMs": 0, "utteranceId": "u1" }
  ```
  ```json
  { "type": "cancel", "utteranceId": "u1" }
  ```
  ```json
  { "type": "end" }
  ```

#### Server → client events (JSON), proposed MVP (landmark-aligned with current repo)
```json
{ "type": "clip_start", "session_id": "s1", "utteranceId": "u1", "phrase_id": "HELLO", "fps": 30 }
```
```json
{
  "type": "frame",
  "session_id": "s1",
  "utteranceId": "u1",
  "phrase_id": "HELLO",
  "frame_index": 0,
  "timestamp_ms": 0,
  "fps": 30,
  "keypoints": [{ "x": 0.1, "y": 0.2, "z": 0.0, "visibility": 1.0 }]
}
```
```json
{ "type": "clip_end", "session_id": "s1", "utteranceId": "u1", "phrase_id": "HELLO" }
```
```json
{ "type": "error", "code": "unknown_phrase", "message": "..." }
```

**Required protocol details to finalize (blocked on pose-protocol agreement):**
- **Frame representation:** landmark keypoints (current) vs bone rotations/quaternions vs hybrid; gesture channel/topic/messages.
- **Schema fields:** `version`, per-frame/clip `confidence`, coordinate space/normalization, hand/face/body partitioning.
- **Cadence/clock sync:** server-paced emission at `fps` vs timestamped frames for client playback; how `startMs` anchors `timestamp_ms`.
- **Clip boundaries:** `frame_index==0` per clip and/or explicit markers (per `pose-protocol-response.md`).
- **Batching:** one frame per WS message vs batched frame arrays / binary container (e.g. `.pose`) for bandwidth efficiency.
- **Input mode:** accept raw text only, gloss tokens, or both; OOV/fingerspelling behavior and interruption/cancellation semantics.
- **Lifecycle:** idle-until-first-frame guarantee, end-of-utterance signaling, reconnect behavior.

**Mapping to repo:** aligns with `AvatarPoseFrame` event semantics and phrase-driven generation; streaming transport and agreed renderer-facing schema are new work.

## 6. Frontend `@inclusaai/api-client` integration checklist

- [ ] Confirm exact method names, request/response TypeScript types, and error shapes for all `/v1/*` endpoints.
- [ ] Add/confirm WS client handlers for `ready|partial|final|error` (ASR) and `clip_start|frame|clip_end|error` (pose).
- [ ] Handle `isFinal`/segment replacement rules and timestamp units consistently.
- [ ] Support vocabulary discovery (`GET /v1/vocabulary`) and model/capability discovery (`GET /v1/models`).
- [ ] Feature-flag streaming endpoints until staging stability/load tests pass.

## 7. Implementation plan (recommended)

1. **Spec alignment (this doc + frontend sign-off):** finalize field names, schemas, auth, and pose representation decisions.
2. **REST parity/facades:** implement `GET /v1/models`, `GET /v1/vocabulary`, `POST /v1/pose`, `POST /v1/translate`, `POST /v1/gloss` (reuse existing service logic/pipelines where possible).
3. **ASR streaming WS:** implement `/v1/transcribe/stream` protocol with partial/final events and integration tests.
4. **Pose streaming WS:** implement `/v1/pose/stream` after pose-protocol decisions; include clock-sync and batching strategy.
5. **Validation:** contract tests, end-to-end staging tests with frontend client, latency/bandwidth/fanout tests for 30fps streaming.

## 8. Open questions for backend/frontend sync

- Is `ai-services` the canonical owner of public Render edge APIs, or should a separate gateway serve them?
- Should ASR use `GET /v1/models`, `GET /v1/formats`, or both? What exact `models` schema does the frontend expect?
- What is the authoritative pose wire format for the frontend renderer (landmarks vs bone rotations, gesture channel, confidence/version)?
- For `/v1/translate`, is `sourceLanguage="auto"` required and what language pairs must ship first?
- For `/v1/gloss`, what gloss/expression taxonomy is required for MVP, and is `/v1/glosa` a required alias?
- What auth, CORS, rate limiting, and max payload/duration limits apply on staging? 
- For WS streams: session lifecycle ownership, reconnection/resume requirements, and SLA targets (latency, jitter, drop tolerance)? 

---

**Suggested next artifact:** convert sections 4–5 into concrete OpenAPI (`openapi.yaml`) and AsyncAPI/protocol markdown once the open questions above are answered, then map each endpoint to implementation owners in this repo.