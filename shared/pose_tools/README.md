# inclusaai-pose-tools

pose-format (`.pose`) interchange for InclusaAI.

This library bridges the [`pose-format`](https://github.com/sign-language-processing/pose)
`Pose` container to InclusaAI's two in-house representations:

- the **wire contract** `inclusaai_contracts.events.PoseKeypoint` (`x, y, z, visibility`), and
- the **51-point skeleton** `inclusaai_sign_vocab.skeleton.SKELETON` (9 upper-body pose
  points + 21 + 21 hand landmarks).

Both sign services use it: `avatar-pose-service` generates `Pose` objects and converts them
to `AvatarPoseFrame`s; `sign-recognition-service` extracts a MediaPipe Holistic `Pose`, subsets
it to the 51-point skeleton, and classifies. Sharing one representation extends the matched-pair
symmetry from "shared vocabulary" to "shared representation."

## Scope — plumbing only

This is transport/representation **plumbing** (ADR-0002). It encodes **no ASL content**: glosses,
authoritative vocabulary, and learned models remain gated on the Deaf-community / linguist
consultation. The `pose_code` reduction is an explicit deterministic **placeholder**, not a real
classifier — real recognition/generation arrives with the learned models.

## API

| Function | Purpose |
|---|---|
| `skeleton_header()` | the shared `PoseHeader` for the 51-point skeleton (cached) |
| `keypoints_to_pose(frames, fps=30)` | wire frames → `Pose` |
| `pose_to_keypoints(pose, frame_index)` | one `Pose` frame → ordered `PoseKeypoint`s |
| `frame_count(pose)` | number of frames |
| `holistic_to_skeleton(holistic)` | MediaPipe Holistic `Pose` (~543 pts) → 51-pt `Pose` |
| `fake_skeleton_pose(num_frames, *, seed)` | deterministic placeholder pose (offline/tests) |
| `pose_code(pose)` / `pose_for_code(code)` | placeholder class-code reduction + its inverse |
| `to_pose_bytes(pose)` / `read_pose_bytes(b)` | `.pose` binary (de)serialization |

## Two skeletons

MediaPipe Holistic (via pose-format) yields ~543 points across `POSE_LANDMARKS` (33),
`FACE_LANDMARKS` (468), `LEFT_HAND_LANDMARKS` (21), `RIGHT_HAND_LANDMARKS` (21), and
`POSE_WORLD_LANDMARKS` (33). `holistic_to_skeleton` keeps 9 upper-body pose points + both hands
= **51**; the face is dropped. Selection uses pose-format's own `Pose.get_components`, so the
output points come out in `SKELETON` order.

## Dependencies

`pose-format>=0.14` pulls in numpy/scipy (still pure-Python, no CUDA). MediaPipe is **not** a
dependency here — this library only names MediaPipe's components/points as strings and operates on
already-built `Pose` objects. MediaPipe lives in `sign-recognition-service` (guarded import).

## Tests

Run from the workspace root (the shared libs resolve in the root venv):

```
uv run pytest shared/pose_tools
```
