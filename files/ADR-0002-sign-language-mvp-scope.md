# ADR-0002: Sign Language MVP Scope — ASL, Constrained Vocabulary, Recognition Descope Candidate

**Status:** Accepted (engineering/product scope) — **pending** Deaf community/linguist consultation before dataset work begins
**Repos affected:** `ai-services`, `inclusaai-ml-research`, `web-apps`, `mobile-app`

## Context
Sign language recognition and generation are the platform's hardest, least-commoditized ML problems. The PRD's MVP scope lists both AI sign language avatar generation and sign language recognition from camera input, but does not specify which sign language(s) or how "full" the generation needs to be.

## Decision
1. **Language: American Sign Language (ASL) only for MVP.**
2. **Generation approach: constrained vocabulary (~150–300 common phrases), not full generative text-to-gloss-to-pose synthesis.**
3. **Recognition (camera → meaning) is the first candidate for descope if timeline pressure hits.** MVP should be architected so it can ship as Hearing→Deaf only (speech→captions/avatar) with Deaf→Hearing via text input as a stopgap, without a rearchitecture later.

## Rationale
- ASL has the largest available labeled dataset ecosystem (WLASL, How2Sign, ASL-LEX) and largest existing research base to build on, and the largest addressable market for a US-first education/enterprise/religious-org customer base.
- Full generative sign avatar output (arbitrary text → linguistically correct sign grammar) is still an open research problem industry-wide. A constrained-vocabulary system with a captions fallback for out-of-vocabulary content is honest, testable, and shippable. A generative system producing linguistically wrong sign grammar (e.g., transliterated word-order signing instead of true ASL grammar) actively damages trust with the community the product serves — this is the single most common failure mode in sign-avatar products.
- Recognition accuracy failures are more visible and embarrassing in a *live* presentation than a limited avatar vocabulary is; if forced to cut scope, cut recognition first.

## Consequences
- `inclusaai-ml-research` dataset acquisition scopes to ASL sources first.
- `ai-services`' `avatar-pose-service` ships as a canned-phrase renderer before any generative pose synthesis work begins.
- The model interface in both repos stays pluggable per language (per the platform's stated scalability goal), even though only one language ships at MVP.
- **This ADR does not authorize dataset acquisition on its own.** Per `inclusaai-ml-research`'s guide, Deaf-community/linguist consultation on data representation, gloss structure, and avatar output correctness is a prerequisite gate before large-scale ASL data work begins — track that consultation as a blocking follow-up item, not a parallel nice-to-have.
