# inclusaai-design-system — Implementation Guide

## 1. Purpose & Scope
Owns the shared, versioned UI component library (`@inclusaai/ui`), design tokens, icons, and Storybook documentation consumed by `web-apps` and (with caveats — see Gaps) `mobile-app`. Given the product's own philosophy — "Inclusive by Default... every component should meet WCAG 2.2" (PRD Section 2/11) — this repo is where that principle either gets built in structurally or gets violated inconsistently across three web apps and a mobile app later.

## 2. Owned Responsibilities
- Core component primitives (buttons, inputs, modals, panels, layout containers)
- **Accessibility-specific components** called out explicitly in the brief: high contrast mode support, font scaling, screen-reader primitives, color-blind-friendly palette
- Design tokens (color, spacing, typography) as the single source of truth — no app repo should hardcode a hex value or px spacing
- Icon library
- Storybook for visual documentation and component-level accessibility testing (axe-core integration)

## 3. Tech Stack
- React + TypeScript (component implementation)
- Tailwind CSS (token-driven — Tailwind config generated from or synced with the token source, not maintained separately)
- Storybook (with `@storybook/addon-a11y` for automated accessibility checks on every component, every PR)
- Published as `@inclusaai/ui` via your internal npm registry, semver'd like every other shared package

## 4. Folder Structure
```
inclusaai-design-system/
├── src/
│   ├── tokens/              # color, spacing, typography — source of truth
│   ├── components/
│   │   ├── primitives/      # Button, Input, Modal, Panel...
│   │   └── accessibility/   # HighContrastToggle, FontScaleControl, ScreenReaderOnly, etc.
│   ├── icons/
│   └── index.ts
├── .storybook/
├── stories/                 # one story per component, with a11y addon enabled
├── package.json
└── .github/workflows/
```

## 5. Contracts
No Kafka/gRPC contracts — this repo's contract is purely the published npm package API (`@inclusaai/ui`) and its accompanying design tokens. Treat component prop APIs with the same semver discipline as any other shared package: breaking a prop signature is a major version bump, and consuming repos (`web-apps`, `mobile-app`) pin explicit versions.

## 6. Dependencies on Other Repos
None inbound — this repo should have zero dependency on any other InclusaAI repo (no importing `platform-backend` types, no session/domain logic). Keep it a pure UI library. `web-apps` and `mobile-app` depend on it, not the reverse.

## 7. Milestones
1. Design tokens + core primitives (Button, Input, Panel, Modal, Layout containers) — unblocks `web-apps` UI work immediately, should be first priority even before full accessibility component set
2. Accessibility-specific components (high contrast, font scaling, screen reader primitives) — needed before `web-apps`' audience app MVP ships, since PRD lists these as MVP-relevant accessibility strategy items
3. Storybook + `a11y` addon wired into CI as a required check, not optional documentation
4. Icon library
5. Mobile compatibility evaluation (see Gaps) — don't block MVP web work on resolving this, but don't let it slide indefinitely either

## 8. Quality Bar
Every component requires: a Storybook story, an automated `axe-core` pass in CI, keyboard-navigation verification, and — given this product's specific audience — testing with actual screen readers (VoiceOver/NVDA), not just automated tooling, since automated a11y checkers catch maybe 30-40% of real issues.

## 9. Decisions (formerly Gaps) — see `inclusaai-docs/docs/adr/`

- **React Native compatibility → tokens-only shared package (option b).** This repo publishes `@inclusaai/design-tokens` as the genuinely cross-platform artifact (colors, spacing, typography, contrast ratios, font-scale steps). `@inclusaai/ui` (the React web component layer built here) is web-only; `mobile-app` builds its own native RN components consuming the same tokens rather than attempting a shared component layer. Trying to force Tailwind-based components into RN tends to produce components that are subtly wrong on mobile and become a permanent maintenance tax — better to do genuine native work on each side against a shared source of truth for the values. See ADR-0004.
- **Theming architecture → light/dark + high-contrast are first-class token dimensions from the first commit.** Confirm the token structure (in `src/tokens/`) supports theme variants structurally before building components against it — retrofitting theming after components exist is the expensive path, and this product's accessibility-first positioning makes high-contrast mode non-negotiable, not a stretch goal.

## 10. New: `@inclusaai/design-tokens` as a separate published package
Per ADR-0004, split token publishing out from `@inclusaai/ui`:
```
inclusaai-design-system/
├── packages/
│   ├── design-tokens/       # published as @inclusaai/design-tokens — platform-agnostic (JSON/JS values, no React)
│   └── ui/                  # published as @inclusaai/ui — React web components, imports design-tokens
```
`mobile-app` depends on `@inclusaai/design-tokens` only. `web-apps` depends on both.
