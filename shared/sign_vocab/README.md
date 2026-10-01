# inclusaai-sign-vocab

The **closed constrained ASL vocabulary** — the single source of truth shared by
`avatar-pose-service` (generation) and `sign-recognition-service` (recognition).

Per [ADR-0002](../../ADR-0002-sign-language-mvp-scope.md), sign-language support in the
MVP is scoped to **one symmetric vocabulary**: the avatar generates from exactly the
set the recognizer classifies against, plus a fingerspelling fallback for anything
outside it. Building generation and recognition against a shared library — rather than
two hand-maintained lists — is what keeps them a *matched pair* instead of drifting
(as they had: `"thank you"` on one side, `"thank-you"` on the other).

## What's here

| Module | Contents |
|---|---|
| `vocabulary` | `PhraseEntry`, `PHRASES`, `PHRASE_BY_ID`, `phrase_ids()`, `match(text)`, `normalize(text)` |
| `fingerspelling` | `FINGERSPELL_ALPHABET`, `fingerspell(text) -> list[str]` |
| `skeleton` | `SKELETON` (ordered joint names), `NUM_KEYPOINTS` — layout only, **no coordinates** |

- `phrase_ids()` is **the closed classification label set** — the recognizer classifies
  into it, the avatar generates from it. Both services key off it, so extending the
  vocabulary here updates both at once.
- `match()` maps free transcript text to a phrase using whole-word (token) subsequence
  matching, preferring the longest surface form (so `"how are you today"` → `how_are_you`,
  not `how`). Out-of-vocabulary text is the caller's cue to fall back to `fingerspell()`.
- `skeleton` carries **names and order only** so this library stays dependency-free;
  pose *coordinates* live in `avatar-pose-service`. Both sides agree on which joints
  exist and in what order, so a generated pose and an observed pose are comparable.

## ⚠️ Scope: starter set, NOT yet authoritative

This ships a small (~55-phrase), clearly-labeled **starter set** whose structure scales
to the ~150–300-phrase target. It exists so the two services can be wired symmetrically
**now**. It is **not** an authoritative ASL resource:

- The `gloss` values are **unverified engineering placeholders** (real ASL glosses are
  not a 1:1 uppercasing of English).
- ADR-0002 makes a **Deaf-community / linguist consultation a blocking prerequisite**
  before authoritative dataset, gloss, and phrase-list work. The curated list and
  verified glosses land *after* that consultation — not from this file.

To extend: add entries to `_PHRASES` / `_NUMBER_WORDS` in `vocabulary.py`. Everything
downstream derives from `phrase_ids()`, so both services stay in lock-step automatically.

Pure Python, no runtime dependencies. Joins the `uv` workspace via the root
`members = ["shared/*"]` glob.
