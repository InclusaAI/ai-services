# web-apps — Implementation Guide

## 1. Purpose & Scope
Hosts the three web applications: **Presenter**, **Audience**, and **Admin**. Kept as one internal monorepo (via Turborepo or Nx) per the brief, since these three apps share the design system, auth flow, and much of the real-time client logic — but each is independently deployable.

## 2. Owned Apps
| App | Users | Core Screens |
|---|---|---|
| `presenter/` | Hearing/Deaf/hard-of-hearing presenters | Create presentation, upload slides, configure accessibility, select communication mode, camera calibration (Deaf presenter journey), start/run session, post-session recording export |
| `audience/` | Attendees | Join (QR/code/link), personalized accessibility preference selection, live presentation view (captions/avatar/gestures/translation), session history |
| `admin/` | Org admins | User/org management, analytics dashboards, billing (reads from `platform-support`) |

## 3. Tech Stack
- Next.js + React + TypeScript
- Tailwind CSS
- TanStack Query (server state — REST calls to `platform-backend`/`platform-support`)
- Zustand (client state — active accessibility channel selections, layout state)
- React Hook Form + Zod (forms + validation, shared schemas ideally sourced from `@inclusaai/shared-types` where the same shape is validated server-side)
- WebSocket client (connects to `fanout-service` in `platform-backend`) for live captions/avatar-pose/translation delivery
- WebRTC client SDK matching whatever `realtime-media-backend` chose (LiveKit client SDK if LiveKit) for audio/video capture and playback
- Avatar rendering: Three.js/React Three Fiber (lightweight, recommended for web) consuming `ai.avatar.pose.frame` data relayed through `fanout-service`

## 4. Folder Structure
```
web-apps/
├── apps/
│   ├── presenter/
│   ├── audience/
│   └── admin/
├── packages/
│   ├── api-client/          # typed REST/WebSocket client wrapping @inclusaai/shared-types
│   ├── avatar-renderer/     # shared Three.js avatar rendering logic (presenter preview + audience view use this)
│   └── layout-engine/       # adaptive layout logic (PRD Section 12: Balanced/Accessibility Focus/Presentation Focus/Adaptive)
├── turbo.json (or nx.json)
└── .github/workflows/
```

**Design note on `layout-engine`:** PRD Section 12 describes multiple named layouts plus fully adaptive resizing based on which accessibility panels are active, and Section 10 requires this to be personalized per participant. This is complex enough UI logic to warrant its own shared package used by both `presenter` (preview) and `audience` (live view), rather than being duplicated per app.

## 5. Contracts

### Consumes (REST, from `platform-backend` / `platform-support`)
- `platform-backend`: `/auth/*`, `/organizations/*`, `/presentations/*`, `/sessions/*`, `/preferences/*`
- `platform-support`: `/billing/*` (admin app only)

### Consumes (WebSocket, from `fanout-service`)
- Personalized per-participant stream: captions, avatar pose frames, gesture data, translation text, TTS audio references — filtered server-side based on that participant's `accessibility_preferences`, so the client just renders whatever arrives rather than filtering itself

### Consumes (WebRTC, from `realtime-media-backend`)
- Media session join/signaling for camera/mic capture (presenter) and presenter video playback (audience, if video is part of the experience)

### Publishes (REST/WebSocket)
- Accessibility preference updates → `preference-service`
- Session/presentation CRUD → `session-service`
- Camera calibration signals (Deaf presenter journey) → `realtime-media-backend` + `vision-quality-service` feedback loop

## 6. Dependencies on Other Repos
- `@inclusaai/shared-types`, `@inclusaai/shared-auth`, `@inclusaai/ui` (design system — **hard dependency**, do not fork or duplicate components locally)
- `inclusaai-infra` for deployment (likely static/edge hosting for Next.js, confirm with infra)

## 7. MVP Milestones (from PRD Section 15)
1. `presenter/`: auth, create presentation, upload PDF/PPT, select communication mode, start session
2. `audience/`: join via QR/code, basic accessibility preference toggle (captions on/off, avatar on/off), live view
3. Live captions rendering (highest priority per MVP scope)
4. Avatar rendering — start with the shared `avatar-renderer` package early since it's needed in both apps and is non-trivial
5. `admin/`: defer most of it — MVP scope doesn't call out advanced admin/analytics; basic org/user management may still be needed to support org invitations in MVP auth flow

## 8. Quality Bar
Standard bar, **plus accessibility is a hard requirement, not a nice-to-have, for this repo specifically**: WCAG 2.2 AA testing (automated via axe-core in CI + manual testing), keyboard navigation testing, screen reader testing on the audience app in particular, since some audience members will be using assistive tech to access an *accessibility* product — that irony can't survive contact with real users.

## 9. Decisions (formerly Gaps) — see `inclusaai-docs/docs/adr/`

- **WebRTC client SDK → LiveKit client SDK.** Unblocked now that `realtime-media-backend` has settled on LiveKit as the SFU. See ADR-0001.
- **Large-screen/kiosk/projector mode → a responsive layout variant within `audience/` and/or `presenter/`**, not a fourth app. Consistent with the `layout-engine` package already being built as shared adaptive-layout logic — kiosk mode is another layout profile, not new application surface.
- **Real user testing with Deaf/hard-of-hearing testers → schedule explicitly against the MVP timeline, not left implicit.** Recommend a testing checkpoint before avatar and layout work is considered MVP-complete, not just before final launch — catching signing-speed/avatar-realism/gloss-grammar issues late is expensive to unwind. Track this as a milestone, not a "nice to have if time allows."
