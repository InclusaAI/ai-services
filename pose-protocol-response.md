# Pose Protocol — ai-services Response

**Status: DRAFT response to `pose-protocol-proposal.md` (web-apps / avatar-engine).**
This is the ai-services side of the same meeting prep. It answers the five open questions
from our repo's perspective, states what we emit today, and proposes a wire contract to
agree on. Nothing here is committed until both developers sign off in the meeting. We have
**not** modified the avatar-engine proposal — this is a companion document.

Cross-references are to this repo (`ai-services`):
- Payload models: `shared/contracts/src/inclusaai_contracts/events.py`
- Skeleton layout: `shared/sign_vocab/src/inclusaai_sign_vocab/skeleton.py`
- Topics: `shared/kafka_clients/src/inclusaai_kafka_clients/topics.py`

---

## 0. TL;DR

1. **What we emit today is landmark _positions_, not bone _rotations_.** `ai.avatar.pose.frame`
   currently carries a list of `{x, y, z, visibility}` MediaPipe-style landmarks. Your renderer
   expects quaternion bone rotations keyed by rig bone name. These are two different
   representations of a body; bridging them is retargeting/IK, not a field rename.
2. **Our headline proposal: ai-services emits landmarks on both channels; avatar-engine owns
   rig-specific retargeting.** Rationale below — the short version is that retargeting needs
   knowledge of your specific rig (`inclusa-body-v1.glb`, bind pose, bone axes), which lives on
   your side, and you already plan to retarget landmarks for hands (`GestureFrame`).
3. **Good news:** your `GestureFrame.landmarks` element is _exactly_ our `PoseKeypoint`. The
   gesture channel is already aligned. And our contract already models `avatar` and `gestures`
   as separate channels, so your two-topic design fits ours.
4. **Cheap alignment items we can commit to now:** add `version` and an optional per-frame
   `confidence` to the frame; register the second topic `ai.avatar.gesture.frame`.
5. **Honest caveat:** our pose generator is still a deterministic **stub** (no real motion data;
   ADR-0002 gates real content on a Deaf-community/linguist consultation). So this is the ideal
   time to fix the _transport contract_ — before either side builds against it.
6. **Interchange bonus:** ai-services now uses `pose-format` internally in both sign services, so we
   can offer its binary `.pose` container (with an official JS reader) as a serialization option
   (§5) — it doesn't change the landmarks recommendation, just how frames are packed on the wire.

---

## 1. What ai-services publishes today (verbatim)

From `shared/contracts/.../events.py`:

```python
class PoseKeypoint(BaseModel):
    x: float
    y: float
    z: float = 0.0
    visibility: float = 1.0

class AvatarPoseFrame(BaseModel):
    """`ai.avatar.pose.frame` — from avatar-pose-service."""
    session_id: str
    phrase_id: str | None = None      # id in the constrained-vocabulary library (ADR-0002)
    frame_index: int
    timestamp_ms: int
    fps: int = 30
    keypoints: list[PoseKeypoint]
```

- `keypoints` is an **ordered list**; index `i` is joint `SKELETON[i]` (see §2). It is **not**
  keyed by name and it is **not** rotations.
- Only **one** avatar topic exists on our side: `ai.avatar.pose.frame`. There is **no**
  `ai.avatar.gesture.frame` yet.
- **`PoseKeypoint` == your `GestureFrame.landmarks[]` element**, field for field
  (`x, y, z, visibility`). This is the one place the two repos already agree exactly.

---

## 2. Our skeleton vs. your rig — why this is retargeting, not renaming

Our shared skeleton (`shared/sign_vocab/.../skeleton.py`) is a signing-relevant subset of
**MediaPipe Holistic**, 51 joints, positions only:

- **9 upper-body pose landmarks:** `nose`, `left/right_shoulder`, `left/right_elbow`,
  `left/right_wrist`, `left/right_hip`.
- **21 landmarks per hand** (MediaPipe Hands topology, includes fingertips):
  `wrist, thumb_cmc…thumb_tip, index_mcp…index_tip, …, pinky_mcp…pinky_tip`.

Your rig (proposal §2) is ~50 **animation bones**, rotations only: `hips, spine, spine1, spine2,
neck, head`, arms, **legs + feet + toes**, and **3-segment fingers** (`thumb1..3`, …), no distal
fingertips.

The two sets do not correspond one-to-one in either direction:

| | ai-services landmarks | your rig bones |
|---|---|---|
| Torso/neck/head | only `nose` (+ shoulders/hips as points) | `spine, spine1, spine2, neck, head` (rotations we can't emit directly) |
| Arms | `elbow`, `wrist` **positions** | `upperArm`, `lowerArm`, `hand` **rotations** (need IK from the positions) |
| Legs/feet/toes | none (upper-body vocabulary) | full leg chain (would stay at bind pose — fine for signing) |
| Fingers | 21 landmarks/hand incl. 4 tips | 15 bones/hand, no tips (map 4 landmarks → 3 rotations, drop tip) |

So converting our output into your `PoseFrame` requires per-bone **inverse kinematics against your
specific rig's bind pose and local axes**. That's the crux of the decision in §4.

_Minor nit for the meeting:_ your §2 caption says "Total bones in rig: 50" but the table lists 52
rows (`6 + 8 + 8 + 15 + 15 = 52`, or `6 spine + 8 arm + 8 leg + 30 finger = 52`). Worth confirming
the true count so both sides key off the same number.

---

## 3. Answers to the five open questions

> Framed as ai-services positions for discussion, not unilateral decisions.

### Q1 — Delta vs. absolute rotations
- **If we emit landmarks (our recommendation): this question moves to your retargeting layer.**
  You compute bone rotations there, so you'd naturally produce **bind-pose deltas** — exactly what
  `bindQuat.multiply(deltaQuat)` wants. Nothing changes in your renderer math, and ai-services
  never needs to know your bind pose (which it shouldn't).
- **If we ever emit bone rotations directly: we would send absolute _local_ (parent-relative)
  quaternions.** ai-services has no knowledge of your captured bind pose and shouldn't couple to
  it. Per your §4 you'll adapt absolutes at ingestion; the adapter is one line of math
  (`delta = bindQuat⁻¹ · absoluteLocal`). So: **absolute local**, and your "we'll write the
  adapter" plan holds.

### Q2 — Frame rate / send cadence
- `AvatarPoseFrame.fps` defaults to **30**; that's our target playback rate.
- **Important nuance: our stream is phrase-driven, not continuous mocap.** A recognized/queued
  phrase produces a **bounded clip** (today ~8 frames per sign, ~4 per fingerspelled letter) at
  the stated fps, then **silence until the next phrase**. Sustained per-session rate is therefore
  low, punctuated by short bursts.
- Pose and (future) gesture frames are **generated together from one phrase**, so for MVP they
  ride the **same cadence and same frame indices** — no reason yet for a faster finger channel. A
  single shared-window buffer on your side is sufficient for MVP; you don't need divergent buffers
  until real captured data drives finer finger motion.
- Every frame carries `frame_index` + `timestamp_ms` for ordering/interpolation.
- Fan-out: our contract flags this as the highest-bandwidth schema (IMPLEMENTATION §5). Because
  it's clip-bounded, let's agree on **max clip length** and whether to **batch N frames per Kafka
  message** vs. one-frame-per-message.

### Q3 — Gesture frame shape: raw landmarks or pre-retargeted?
- **Raw MediaPipe landmarks.** And they're already aligned: your `GestureFrame.landmarks` element
  is our `PoseKeypoint`. Our hand layout is the full 21-landmark MediaPipe Hands topology per hand.
- You retarget 21 landmarks → your 15 finger bones (dropping the 4 distal tips your rig lacks).
  This is consistent with the overall recommendation (§4): we emit landmarks, you retarget.

### Q4 — Confidence / quality field
- Today `AvatarPoseFrame` has **no per-frame confidence**; each `PoseKeypoint` carries per-point
  `visibility ∈ [0,1]` (MediaPipe occlusion semantics). Our sibling `SignRecognitionResult`
  **does** carry `confidence: float | None`.
- **We'll add a per-frame `confidence: float | None` in `[0,1]`** (field name and range as you
  suggested; `null` when unknown) for your render-gating / hold-last-good-pose logic.
- Honest caveat on semantics: for **generated** poses (current path) the pose is deterministic
  from a phrase, so "confidence" really means the **upstream recognition confidence**, propagated
  from `SignRecognitionResult.confidence`. For a future captured/learned path it becomes a real
  per-frame model score. Per-keypoint `visibility` stays for occlusion.

### Q5 — Stream start / session-start guarantee
- Frames carry `session_id` and a monotonic `frame_index`; a clip carries an optional `phrase_id`.
  We do **not** emit a "stream started" sentinel today.
- Kafka gives no connection-time delivery guarantee, so the robust client assumption is
  **"idle until the first message arrives"** (your default). We'll guarantee:
  - `frame_index` starts at **0** for each clip;
  - a **new clip** is signalled by `frame_index == 0` (and/or a change in `phrase_id`).
- If you want an explicit boundary we can add a lightweight **clip start/end marker** rather than
  relying on connection semantics. Let's agree on the clip-boundary convention.

---

## 4. The real decision: who owns landmark → bone retargeting?

Everything above is easy. This is the one that needs both developers.

**Principle we're arguing from: retargeting is rig-specific knowledge and should live where the
rig lives.** Converting landmarks to bone rotations needs the bind pose, bone hierarchy, bone
lengths, and local-axis conventions of `inclusa-body-v1.glb` + `bone-mapping.ts` — all of which
are web-apps assets. If ai-services owned retargeting, the inference service would depend on a
frontend art asset and break every time an artist re-exports the GLB or a character is swapped.
That inverts the dependency the wrong way.

**Recommendation: ai-services emits landmarks on both channels; avatar-engine owns retargeting.**

Reasons:
1. Keeps ai-services **rig-agnostic** (correct architectural boundary — inference emits a portable
   interchange format, the client adapts to its own rig).
2. You **already** plan to retarget landmarks for hands (`GestureFrame` is raw landmarks) —
   extending the same approach to the body keeps one retargeting implementation in one place.
3. **~Zero schema change** for us: our current output already matches the landmark shape.
4. Your §4 already commits you to owning an **ingestion adapter**.

**Fair counter-argument (worth airing):** `mobile-app` is a second consumer. If ai-services
centralized bone-rotation output, web and mobile wouldn't each reimplement retargeting. This only
wins if **both platforms share exactly one rig**; the moment rigs diverge, landmarks are strictly
better (each retargets to its own rig). And shared retargeting can instead be a shared TS package
(design-system or a small avatar lib) consumed by both clients — reuse without coupling
ai-services to a rig.

**Proposed path:** ship **landmarks-on-both now** (unblocks both teams, matches today's output,
keeps us decoupled). Keep a **documented option** to add a centralized `bones`-shaped channel
later *iff* web + mobile converge on one rig **and** retargeting is proven a bottleneck.

**Asymmetry to resolve at the meeting:** your §1 types have `PoseFrame` = bone rotations but
`GestureFrame` = raw landmarks. Under the recommendation, the body would also be landmark-shaped
(you retarget the body just like the hands). If you specifically want bone rotations for the body
but landmarks for hands, let's talk through why the channels differ and who retargets which.

---

## 5. Proposed wire contract (for the meeting to react to)

Both frames stay landmark-shaped; additions marked `# NEW`. This is a minimal delta from today's
`AvatarPoseFrame` and gives you your `GestureFrame` verbatim on a real topic.

```python
# ai.avatar.pose.frame  — upper-body pose landmarks
class AvatarPoseFrame(BaseModel):
    version: int = 1                       # NEW  (matches your PoseFrame.version)
    session_id: str
    phrase_id: str | None = None
    frame_index: int                       # 0 at each clip start (Q5)
    timestamp_ms: int
    fps: int = 30
    confidence: float | None = None        # NEW  [0,1], null if unknown (Q4)
    keypoints: list[PoseKeypoint]          # SKELETON order; body-pose subset

# ai.avatar.gesture.frame  — NEW topic; == your GestureFrame + Kafka envelope fields
class AvatarGestureFrame(BaseModel):
    version: int = 1                       # NEW
    session_id: str
    frame_index: int
    timestamp_ms: int
    fps: int = 30
    confidence: float | None = None        # NEW
    landmarks: list[PoseKeypoint]          # 21 left + 21 right, MediaPipe Hands order
```

Registering the second topic is low-cost on our side: `ai.avatar.gesture.frame` slots into
`topics.py` + `schema_registry.py` alongside the existing pose topic, and our
`AccessibilityChannel` already distinguishes `avatar` from `gestures`.

### Interchange option: pose-format `.pose` as the on-the-wire container

Orthogonal to the landmarks-vs-bones question (§4) is *how frames are serialized*. Worth tabling
because **ai-services already uses [`pose-format`](https://github.com/sign-language-processing/pose)
`Pose` as its internal representation** in both sign services (via `shared/pose_tools`), so emitting
its binary `.pose` container is essentially free on our side:

- **`.pose` is a compact binary format with an official [JS/TS reader](https://github.com/sign-language-processing/pose)**
  (`pose-format` on npm) — the frontend could consume poses directly, no bespoke JSON parsing.
- It self-describes its **header** (component/point names, dimensions, fps), so the
  holistic-vs-skeleton layout question (§2) travels *with* the data instead of in a side agreement.
- It naturally packs **multi-frame clips** (our phrase-driven bursts, Q2) into one payload, which
  fits batching better than one-JSON-frame-per-message.

Caveat to agree on: our `.pose` header advertises the **51-point SKELETON** layout (9 pose + 21 + 21),
*not* full MediaPipe Holistic — so both sides key off the same component/point ordering. This is an
option to weigh, **not** a change to the landmarks-on-both recommendation (§4): whether frames travel
as JSON `PoseKeypoint` lists or `.pose` bytes, they stay landmark-shaped and the retargeting boundary
is unchanged.

---

## 6. What ai-services can commit to, and when

| Item | Cost | When |
|---|---|---|
| Add `version` + `confidence` to the frame | trivial | on agreement |
| Register `ai.avatar.gesture.frame` + split hands onto it | small | on agreement |
| Guarantee `frame_index == 0` clip-start convention | trivial | on agreement |
| Emit landmarks on both channels (matches today) | ~none | now |
| Emit rig-ready **bone rotations** (retargeting/IK server-side) | **large** — needs your rig spec (bind pose, hierarchy, axes) as an input, and couples us to the GLB | only if §4 goes that way |
| Real motion data / verified glosses | out of scope | ADR-0002 consultation gate |

---

## 7. Requests back to the avatar-engine side

1. Confirm the true rig bone count (§2 says 50 vs. 52 listed).
2. Confirm you'll own retargeting for the **body** as well as hands (§4) — or make the case for
   server-side bone rotations, in which case publish the rig contract (bind-pose quaternions per
   bone, hierarchy, local-axis convention, coordinate handedness/units) as an ai-services input.
3. Confirm the clip-boundary convention (`frame_index == 0` / `phrase_id` change) is enough, or
   specify a sentinel.
4. Confirm cadence expectations given our **phrase-driven, clip-bounded** stream (not continuous),
   and your preference on **batching frames per Kafka message**.

---

_Meta: `pose-protocol-proposal.md` is a web-apps artifact (it references `packages/avatar-protocol`,
`packages/avatar-scenes`, `inclusa-body-v1.glb`) currently sitting untracked in this repo. Suggest the
agreed contract ultimately lands in `inclusaai-docs` or the shared kafka-contracts package rather than
either app repo. This response left the proposal untouched._
