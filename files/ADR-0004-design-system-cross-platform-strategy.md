# ADR-0004: Design System Cross-Platform Strategy — Tokens-Only Shared Package

**Status:** Accepted
**Repos affected:** `inclusaai-design-system`, `web-apps`, `mobile-app`

## Context
`@inclusaai/ui`, the design system's React component library, is built with Tailwind CSS and targets web (`web-apps`). React Native (`mobile-app`) cannot consume Tailwind-based web components as-is. Three options were considered:
(a) build genuinely cross-platform components from the start using `react-native-web` conventions,
(b) ship design tokens only as a shared package, with native components built independently per platform,
(c) accept two fully independent component sets with no shared package at all.

## Decision
**Option (b): tokens-only shared package.** `@inclusaai/design-tokens` (colors, spacing, typography scale, contrast ratios, font-scale steps) is published as a platform-agnostic package with no React dependency. `@inclusaai/ui` (React web components) consumes it and remains web-only. `mobile-app` builds native React Native components consuming `@inclusaai/design-tokens` directly.

## Rationale
- Forcing Tailwind-based components into React Native via compatibility shims (`react-native-web` and similar) tends to produce components that are subtly wrong on mobile — spacing, touch targets, and platform-native interaction patterns don't map cleanly — and becomes a permanent maintenance tax as both platforms evolve.
- Genuine native component work on each platform, against a shared source of truth for values, is more upfront work but avoids fighting the framework indefinitely.
- Mobile is explicitly post-MVP per the PRD roadmap, so there's runway to do this properly rather than under time pressure.

## Consequences
- `inclusaai-design-system` restructures into two published packages: `@inclusaai/design-tokens` (platform-agnostic) and `@inclusaai/ui` (web components, depends on design-tokens).
- `mobile-app` depends on `@inclusaai/design-tokens` only, and owns its own native component implementations.
- Theming (light/dark, high-contrast) must be a first-class dimension of `@inclusaai/design-tokens` structure from the first commit — both platforms' components depend on this being right early, since retrofitting theming after components exist on both platforms is expensive twice over.
- Accept some visual/interaction drift risk between web and mobile components over time since they're independently implemented; mitigate with shared Storybook-equivalent visual review process across both, if resourcing allows.
