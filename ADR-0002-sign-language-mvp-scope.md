# ADR-0002: Sign Language MVP Scope — ASL, Symmetric Constrained Vocabulary (Generation + Recognition)

**Status:** Accepted (engineering/product scope) — **pending** Deaf community/linguist consultation before dataset work begins
**Repos affected:** `ai-services`, `inclusaai-ml-research`, `web-apps`, `mobile-app`
**Supersedes:** earlier version of this ADR, which recommended deferring recognition to post-MVP with a text-input stopgap. That approach was rejected on review — see "Why the earlier version was wrong," below.

## Context
Sign language recognition and generation are the platform's hardest, least-commoditized ML problems. The PRD's MVP scope lists both AI sign language avatar generation and sign language recognition from camera input, but does not specify which sign language(s) or how "full" either capability needs to be.

## Decision
1. **Language: American Sign Language (ASL) only for MVP.**
2. **Both generation and recognition are scoped to the same constrained vocabulary — ~150–300 common presentation/classroom phrases (greetings, transitions, common Q&A, numbers) plus fingerspelling.** This is a deliberate symmetry: the avatar generates from this set, and the recognizer classifies against this same closed set. Fingerspelling recognition (a bounded ~26-symbol problem) covers content outside the phrase vocabulary. Full open-vocabulary, continuous sign language translation in either direction is the post-MVP research target.
3. **Recognition stays in MVP scope.** It is not deferred, and it is not replaced with a text-input fallback for Deaf presenters.

## Why the earlier version of this ADR was wrong
An earlier pass at this decision recommended deferring recognition post-MVP and suggested Deaf presenters use text input as a stopgap. Both calls were mistakes, caught on review:

- **Text input as a "stopgap" contradicts the product's own stated purpose.** The platform's own positioning explicitly names the failure it exists to fix: existing tools fail because presenters with hearing impairments "lack tools that translate their visual communication back into spoken or written language." Asking a Deaf presenter — whose first language is ASL, not English — to type instead of sign is the exact burden the product claims to remove. Recommending it as InclusaAI's own fallback undercut the platform's accessibility-first premise.
- **Cutting recognition removes the actual differentiator, not a nice-to-have.** The platform's stated positioning is bidirectional communication, explicitly contrasted against tools that "focus only on captioning." Speech→captions/avatar alone is not bidirectional — it's a captioning tool. Cutting recognition doesn't trim scope, it removes the reason the product is differentiated from what already exists.
- **The difficulty was overestimated by conflating two different problems.** Open-vocabulary continuous sign language translation (arbitrary signing → arbitrary text) is genuinely research-grade. But recognition against a known, closed vocabulary of ~150–300 phrases — the same set generation is already constrained to — is closed-set sign classification, a substantially more tractable and well-benchmarked problem, closer to gesture classification than to translation. Generation was correctly scoped down to something achievable; recognition should get the same treatment instead of being cut.

## Rationale for what remains
- ASL has the largest available labeled dataset ecosystem and existing research base among sign languages generally (see the global resource-availability note below), and the largest addressable market for a US-first education/enterprise/religious-org customer base.
- Full generative, open-vocabulary sign output (either direction) is still an open problem industry-wide. A constrained, symmetric vocabulary with a fingerspelling/captions fallback for anything outside it is honest, testable, and genuinely bidirectional — without overclaiming capability the ML doesn't support yet.

## Global resource-availability note — why "pluggable to additional sign languages" will move at very different speeds per language
The platform's architecture keeps the model interface pluggable per sign language, which is the right call — but it's worth being explicit that **labeled data and tooling availability are extremely uneven across sign languages globally**, and this will directly gate how fast additional languages can realistically be added after ASL:

- **Relatively better-resourced**: ASL (WLASL, MS-ASL, How2Sign, ASL-LEX), and German Sign Language/DGS (RWTH-PHOENIX-Weather 2014T, though domain-specific to weather broadcasts). These have public, labeled, research-usable datasets and an active academic community.
- **Thin but present**: British Sign Language (BSL Corpus exists but is smaller and less ML-ready than ASL's datasets), a handful of other European sign languages with academic corpora not originally built for ML training.
- **Little to no public labeled data or open tooling**: the vast majority of the world's ~300 sign languages — including Indian Sign Language (despite India's large Deaf population), Nigerian Sign Language and most African sign languages, most Southeast Asian sign languages, and many others. For these, there is often no public dataset, no pretrained model to fine-tune from, and in some cases limited prior computational linguistics work on the language's grammar at all.
- **Practical consequence**: expanding beyond ASL is not primarily an engineering lift once the pluggable interface exists — it's a **data acquisition and community-partnership problem**, often starting from near zero. For most future languages, this will look less like "swap in a new model" and more like "fund and run an original data collection effort with native signers," which is a materially different roadmap item (cost, timeline, and partnership model) than the architecture diagrams suggest on their own. Set expectations with stakeholders accordingly — "the architecture supports it" is true and worth stating; "so we can add language N quickly" is very likely false for most languages beyond the first few.

## Consequences
- `inclusaai-ml-research` dataset acquisition scopes to ASL sources first, for both the generation vocabulary and the matching recognition classifier.
- `ai-services`' `avatar-pose-service` and a new/expanded scope for its recognition counterpart both ship against the same constrained vocabulary — build these as a matched pair, not as independently scoped features.
- The model interface in both repos stays pluggable per language, but the roadmap for any language beyond ASL should be planned as a data-partnership effort, not a swap-in engineering task — reflect this in any external-facing roadmap communication.
- **This ADR does not authorize dataset acquisition on its own.** Per `inclusaai-ml-research`'s guide, Deaf-community/linguist consultation on data representation, gloss structure, and recognition/avatar output correctness is a prerequisite gate before large-scale ASL data work begins — track that consultation as a blocking follow-up item, not a parallel nice-to-have.
