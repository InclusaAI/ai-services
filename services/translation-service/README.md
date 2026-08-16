# translation-service

Translates transcript segments into a participant's target language.

## I/O

| | Topic / event key | Payload |
|---|---|---|
| Consumes | `ai.transcript.segment` | `TranscriptSegment` |
| Consumes | `accessibility.preference.updated` | handled by the base pipeline (drives gating) |
| Publishes | `ai.translation.result` | `TranslationResult` |
| Publishes | `ai.usage.aggregate` (periodic) | `UsageAggregate` (unit = `translation`) |

**Preference-gated** on the `translation` channel: if no participant in a session
has translation enabled, the work is skipped (`output_channel = TRANSLATION`).

> TODO(prefs): the scaffold translates to a single `default_target_language`. In
> production, fan out one translation per distinct participant target language.

See `services/asr-service` for the fuller reference (incl. the optional gRPC servicer).
