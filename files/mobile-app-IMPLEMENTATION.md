# mobile-app — Implementation Guide

## 1. Purpose & Scope
React Native app for iOS/Android. Per both the brief and PRD, mobile is explicitly **not** in MVP scope ("Mobile applications for iOS and Android" is listed under Future Roadmap, Section 16) — this repo should exist and be scaffolded, but active feature development should trail the web apps by design, not by accident.

Kept as its own repo (not inside `web-apps`) because its runtime, release process (app store review cycles), and native platform requirements differ substantially — confirmed in the brief.

## 2. Scope When Active
Primarily an **audience-first** experience initially — joining and viewing presentations on a phone (QR/code join, live captions/avatar/translation view) is the highest-value mobile use case. Presenter-side mobile (running a live presentation from a phone) is a much heavier lift (camera calibration for sign language presenting, screen-share/slide control) and should be scoped as a later phase within this repo, not attempted in v1.

## 3. Tech Stack
- React Native + TypeScript
- React Navigation
- TanStack Query (mirrors `web-apps` server-state pattern for consistency)
- Zustand (client state)
- React Hook Form + Zod
- WebSocket client to `fanout-service` (same contract as `web-apps`)
- Avatar rendering: this is the one place the stack should **not** just mirror web — Three.js/WebGL performance on mobile React Native is a real constraint. Evaluate `react-native-webgl`/`expo-gl` vs. a native module early; don't assume the web avatar renderer just ports over.

## 4. Folder Structure
```
mobile-app/
├── src/
│   ├── screens/
│   │   ├── join/
│   │   ├── live-session/
│   │   └── history/
│   ├── components/
│   ├── state/
│   ├── api/               # wraps @inclusaai/shared-types, mirrors web-apps/packages/api-client patterns
│   └── avatar-renderer/    # mobile-specific implementation, NOT a copy-paste of web-apps' Three.js package
├── ios/
├── android/
└── .github/workflows/
```

## 5. Contracts
Same contracts as `web-apps` audience app: REST to `platform-backend` (`/sessions/*`, `/preferences/*`), WebSocket to `fanout-service` for personalized live content, WebRTC to `realtime-media-backend` for media playback.

## 6. Dependencies on Other Repos
- `@inclusaai/shared-types`, `@inclusaai/shared-auth`, `@inclusaai/ui` — **note**: `@inclusaai/ui` (design system) needs to confirm React Native compatibility or provide a parallel token-only package (colors/spacing/typography without web-specific DOM components) — most component libraries built for web don't run as-is in React Native. Flag this with `inclusaai-design-system` explicitly.
- `inclusaai-infra` for CI/CD (app store deployment pipelines are meaningfully different from container deploys — confirm GitHub Actions setup accounts for this)

## 7. Milestones
Given explicit post-MVP status:
1. Scaffold app, auth, join flow (can start anytime, low risk, unblocks later work)
2. Live captions view (mirrors web MVP priority)
3. Avatar view (pending the mobile rendering evaluation above)
4. Presenter-side mobile — explicitly out of scope until audience-side is stable in production

## 8. Quality Bar
Standard bar plus: device-farm testing across a real spread of iOS/Android versions and screen sizes (accessibility features like font scaling and screen reader support behave differently per OS version), and app store review compliance built into CI (privacy manifest requirements, permissions justification for camera/mic access).

## 9. Decisions (formerly Gaps) — see `inclusaai-docs/docs/adr/`

- **Design system compatibility → tokens-only shared package, native RN components built here.** `@inclusaai/design-tokens` (colors, spacing, typography, contrast ratios, font-scale steps) is the genuinely shared package; `inclusaai-design-system` builds the web component layer, this repo builds native RN components consuming the same tokens. More upfront component work than trying to force web components into RN, but avoids a permanent maintenance tax from compatibility shims. Given mobile is explicitly post-MVP, there's time to do this properly. See ADR-0004.
- **Avatar rendering on mobile → dedicated technical spike required before committing to an approach.** Do not assume the web Three.js renderer ports over — evaluate `react-native-webgl`/`expo-gl` vs. a native module as an explicit spike, scheduled ahead of any mobile avatar UI work.
- **Presenter-side sign-language camera calibration on mobile → treat as web/desktop-only for now.** Sign language presenting likely needs a larger, stable, hands-free camera frame; phone-in-hand isn't a strong fit. Mobile presenter-side work (once it starts, post audience-side stability) should scope this out explicitly rather than attempting parity with the desktop presenter journey.
