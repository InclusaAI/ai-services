# translation-service

Translates transcript segments into a participant's target language.

## I/O

| | Topic / event key | Payload |
|---|---|---|
| Consumes | `ai.transcript.segment` | `TranscriptSegment` |
| Consumes | `ai.sign.recognition.result` | `SignRecognitionResult` — the Deaf-presenter leg |
| Consumes | `accessibility.preference.updated` | handled by the base pipeline (drives gating) |
| Publishes | `ai.translation.result` | `TranslationResult` |
| Publishes | `ai.usage.aggregate` (periodic) | `UsageAggregate` (unit = `translation`) |

**Preference-gated** on the `translation` channel: if no participant in a session
has translation enabled, the work is skipped (`output_channel = TRANSLATION`) — on
both input legs.

### The Deaf-presenter leg

`ai.sign.recognition.result` is the sign-recognition service's output. Consuming it
here is what closes the reverse direction: a Deaf presenter signs → sign-recognition
recognizes the closed-set gloss → **this service** renders it into a spoken language →
avatar-pose signs it back out so hearing participants can see what was said. Without
this subscription the recognizer's output had no consumer anywhere in the platform.

For a recognized sign the translatable content is the **`gloss`**, falling back to the
phrase `label` when the recognizer emitted no gloss. `segment_id` is carried through
either way, so a translation correlates back to the exact upstream segment.

Two caveats, both consequences of ADR-0002 scoping rather than defects here:

* **Glosses are English placeholder text** until the Deaf-community/linguist
  consultation lands, so the MT `source` is `sign_gloss_source_language` (default
  `en`) and *not* the sign language code — `ASL` is not a text language pair. A gloss
  language is not a sign language; revisit when real glosses land.
* **A fingerspelled window carries a single letter** (sign-recognition emits one letter
  per gesture window), so translating one in isolation yields a lone letter rather than
  a word. Assembling letters into words belongs with the recognizer's window
  aggregation, not here.

> Downstream caveat worth knowing: avatar-pose matches `translated_text` against a
> vocabulary whose surface forms are English, so a non-English translation falls through
> to fingerspelling rather than matching a phrase. Fixing that needs either a
> per-language vocabulary or gloss-keyed lookup — an ADR-0002 follow-up.

> TODO(prefs): the scaffold translates to a single `default_target_language`. In
> production, fan out one translation per distinct participant target language.

See `services/asr-service` for the fuller reference (incl. the optional gRPC servicer).
