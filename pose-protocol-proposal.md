# Pose Protocol Proposal — Meeting Prep Document

**Status: DRAFT — awaiting review and agreement with ai-services developer.**  
**Do not treat anything in this document as finalized. Phase 1 of the avatar-engine
implementation MUST NOT begin until a human confirms the meeting happened and provides
the real, agreed frame shapes.**

---

## 1. Current PoseFrame and GestureFrame Types (verbatim from `packages/avatar-protocol/src/index.ts`)

```typescript
import type { EventEmitter } from 'eventemitter3';

// --- Data Shapes ---

export type Quaternion = { x: number; y: number; z: number; w: number };
export type Vector3 = { x: number; y: number; z: number };

/**
 * Defines the transformation for a single bone.
 * Rotation is mandatory for any meaningful pose. Position and scale are optional.
 */
export type BoneTransform = {
  rotation: Quaternion; // Rotation is no longer partial
  position?: Vector3;   // Position is no longer partial
  scale?: Vector3;      // Scale is no longer partial
};

export type PoseFrame = {
  version: 1;
  timestamp: number;
  bones: Record<string, Partial<BoneTransform>>; // Allow partial transforms per bone
};

// --- Stream Source Interface ---

/**
 * Defines the contract for a source of pose frames.
 * A source must provide methods to start/stop and listen for 'frame' events.
 */
export interface PoseFrameSource {
  on(event: 'frame', listener: (frame: PoseFrame) => void): this;
  off(event: 'frame', listener: (frame: PoseFrame) => void): this;
  start(): void;
  stop(): void;
}

// --- Gesture & Topics (placeholders) ---

export type GestureFrame = {
  timestamp: number;
  sessionId: string;
  landmarks: Array<{
    x: number;
    y: number;
    z: number;
    visibility: number;
  }>;
};

export type AvatarTopic = 'ai.avatar.pose.frame' | 'ai.avatar.gesture.frame';
export const AVATAR_POSE_TOPIC = 'ai.avatar.pose.frame' as const;
export const AVATAR_GESTURE_TOPIC = 'ai.avatar.gesture.frame' as const;
export const AVATAR_TOPICS = [AVATAR_POSE_TOPIC, AVATAR_GESTURE_TOPIC] as const;
```

---

## 2. All Bone Names Supported by the Rig (from `packages/avatar-scenes/src/bone-mapping.ts`)

The table below maps every **canonical bone name** (used in `PoseFrame.bones` keys) to
the corresponding **GLB joint name** in the current rigged model (`inclusa-body-v1.glb`).
Any bone name sent by the ai-services backend that is NOT in this list will be silently
ignored by the renderer.

| Canonical Name (PoseFrame key) | GLB Joint Name |
|---|---|
| **Body / Spine** | |
| `hips` | `hips_JNT` |
| `spine` | `spine_JNT` |
| `spine1` | `spine1_JNT` |
| `spine2` | `spine2_JNT` |
| `neck` | `neck_JNT` |
| `head` | `head_JNT` |
| **Left Arm** | |
| `leftShoulder` | `l_shoulder_JNT` |
| `leftUpperArm` | `l_arm_JNT` |
| `leftLowerArm` | `l_forearm_JNT` |
| `leftHand` | `l_hand_JNT` |
| **Right Arm** | |
| `rightShoulder` | `r_shoulder_JNT` |
| `rightUpperArm` | `r_arm_JNT` |
| `rightLowerArm` | `r_forearm_JNT` |
| `rightHand` | `r_hand_JNT` |
| **Left Leg** | |
| `leftUpperLeg` | `l_upleg_JNT` |
| `leftLowerLeg` | `l_leg_JNT` |
| `leftFoot` | `l_foot_JNT` |
| `leftToeBase` | `l_toebase_JNT` |
| **Right Leg** | |
| `rightUpperLeg` | `r_upleg_JNT` |
| `rightLowerLeg` | `r_leg_JNT` |
| `rightFoot` | `r_foot_JNT` |
| `rightToeBase` | `r_toebase_JNT` |
| **Left Hand Fingers** | |
| `leftThumb1` | `l_handThumb1_JNT` |
| `leftThumb2` | `l_handThumb2_JNT` |
| `leftThumb3` | `l_handThumb3_JNT` |
| `leftIndex1` | `l_handIndex1_JNT` |
| `leftIndex2` | `l_handIndex2_JNT` |
| `leftIndex3` | `l_handIndex3_JNT` |
| `leftMiddle1` | `l_handMiddle1_JNT` |
| `leftMiddle2` | `l_handMiddle2_JNT` |
| `leftMiddle3` | `l_handMiddle3_JNT` |
| `leftRing1` | `l_handRing1_JNT` |
| `leftRing2` | `l_handRing2_JNT` |
| `leftRing3` | `l_handRing3_JNT` |
| `leftPinky1` | `l_handPinky1_JNT` |
| `leftPinky2` | `l_handPinky2_JNT` |
| `leftPinky3` | `l_handPinky3_JNT` |
| **Right Hand Fingers** | |
| `rightThumb1` | `r_handThumb1_JNT` |
| `rightThumb2` | `r_handThumb2_JNT` |
| `rightThumb3` | `r_handThumb3_JNT` |
| `rightIndex1` | `r_handIndex1_JNT` |
| `rightIndex2` | `r_handIndex2_JNT` |
| `rightIndex3` | `r_handIndex3_JNT` |
| `rightMiddle1` | `r_handMiddle1_JNT` |
| `rightMiddle2` | `r_handMiddle2_JNT` |
| `rightMiddle3` | `r_handMiddle3_JNT` |
| `rightRing1` | `r_handRing1_JNT` |
| `rightRing2` | `r_handRing2_JNT` |
| `rightRing3` | `r_handRing3_JNT` |
| `rightPinky1` | `r_handPinky1_JNT` |
| `rightPinky2` | `r_handPinky2_JNT` |
| `rightPinky3` | `r_handPinky3_JNT` |

**Total bones in rig:** 50 (6 spine/head + 8 arms + 8 legs + 15 left-hand fingers + 15 right-hand fingers — note: finger joints are 3 segments × 5 fingers × 2 hands = 30 finger joints; `leftPinky4` / `rightPinky4` distal tips are NOT in the rig).

---

## 3. Open Questions for the Meeting

> **These are questions, not answers. Do NOT interpret any wording below as implying
> a preferred direction — list them neutrally for discussion.**

1. **Delta vs. absolute rotations**: Does `ai.avatar.pose.frame` send bone rotations as
   *deltas from the model's bind/T-pose*, or as *absolute local/world quaternions*?
   The avatar-engine currently assumes **deltas** (it composes each rotation on top of
   the captured bind-pose quaternion via `bindQuat.multiply(deltaQuat)`). If the service
   sends absolute local rotations instead, the composition math must change — this MUST
   be confirmed before Phase 1 locks in the schema, not assumed.

2. **Frame rate / send cadence**: What is the expected send interval for
   `ai.avatar.pose.frame` and `ai.avatar.gesture.frame` respectively — are they sent at
   the same cadence (e.g. both at 30 fps), or different (e.g. pose at 30 fps, gesture
   at 60 fps because it drives fine finger articulation)? This determines whether a
   single `FrameBuffer` with a shared window is appropriate, or whether pose and gesture
   need separate buffers with different window sizes.

3. **Gesture frame shape — raw landmarks or pre-retargeted bone rotations?**: For
   `ai.avatar.gesture.frame`, is the payload 21 raw MediaPipe-style hand landmarks
   per hand (x/y/z/visibility per landmark, requiring avatar-engine to perform
   landmark-to-bone retargeting), or pre-resolved finger bone rotations in the same
   `bones: Record<string, BoneTransform>` format as `PoseFrame` (requiring no
   retargeting on avatar-engine's side)? This materially changes the scope and
   implementation of Phase 3.

4. **Confidence / quality field**: Does every frame include a per-frame confidence
   score (e.g. `confidence: number` in [0, 1]) that avatar-engine should use to decide
   whether to render the frame or hold the last known good pose? If so, what is the
   expected field name and range?

5. **Stream start / session start guarantee**: At session start, is there a guaranteed
   first frame immediately on connection, or should the avatar-engine client assume
   "no data yet" (i.e. connectionState = 'idle') until the first message arrives?
   Does the service emit a "stream started" sentinel message before pose frames begin?

---

## 4. What We Will NOT Change Regardless of the Answers

The following are internal avatar-engine implementation choices that the ai-services
team's answers should not require us to alter:

- **Bind-pose-delta composition math** (`bindQuat.multiply(deltaQuat)` in `BodyAvatar`
  and `HandGestureAvatar`): the renderer always composites incoming deltas on top of
  the model's captured bind pose. If the service sends absolutes, we will write an
  adapter at the ingestion boundary — we will NOT change the renderer's internal math.
- **`PoseFrameSource` interface contract** (`start()`, `stop()`, `on('frame', …)`,
  `off('frame', …)`): any real AI stream client (`AvatarStreamClient`) and all
  mock/test sources will continue to implement this interface. The rendering components
  only depend on this interface, not on any specific transport.
- **Two-topic design** (`ai.avatar.pose.frame` vs. `ai.avatar.gesture.frame`): the
  two-channel separation between full-body pose and hand-gesture data is an
  internal architectural decision. Whether the service merges them into one stream
  or keeps them separate, avatar-engine will continue to handle them as distinct
  logical channels internally.

---

## 5. Next Steps

- [ ] Human confirms this doc was reviewed with the ai-services developer
- [ ] Human pastes (or links) the real, agreed `PoseFrame` / `GestureFrame` shapes into
      the IDE session to trigger Phase 1
- [ ] Phase 1 implementation begins ONLY after the above two steps are complete
