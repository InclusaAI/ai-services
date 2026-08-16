# tts-service

Text-to-speech for the Deaf→Hearing direction: turns translated text into audio
chunks a hearing participant hears.

## I/O

| | Topic / event key | Payload |
|---|---|---|
| Consumes | `ai.translation.result` | `TranslationResult` |
| Consumes | `accessibility.preference.updated` | handled by the base pipeline (drives gating) |
| Publishes | `ai.tts.audio.chunk` | `TtsAudioChunk` |
| Publishes | `ai.usage.aggregate` (periodic) | `UsageAggregate` (unit = `tts_chunk`) |

**Preference-gated** on the `tts` channel (`output_channel = TTS`).

The engine may be a self-hosted model or a third-party provider behind the same
interface (ADR-0009) — usage is metered identically either way. See
`services/asr-service` for the fuller reference (incl. the optional gRPC servicer).
