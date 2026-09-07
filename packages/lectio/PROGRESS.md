# Lesson Builder Merge Progress

## Xplore 0.6.0 — Active

The active `xplore` work is tracked in
`docs/project/runs/2026-07-30-xplore-lectio-0.6.0.md`. It adds diagnostic quiz metadata,
section-level concept-card provenance, and the diagnostic answer-key component without changing
existing component behaviour.

L1 is complete: `QuizOption.diagnoses` is optional in the TypeScript and Zod contracts, is
documented as metadata-only, has a focused passing test, and does not appear in learner-facing
renderers.

L2 is complete: `SectionContent.card_id` and `SectionContent.varies_on` are optional metadata
fields and no component branches on either value.

L3 is complete: the `answer-key` component is registered across the component module, runtime,
teacher builder, document interchange, and public export surfaces. Its focused integration suite,
type check, production build, and contract export all pass.

L4 is complete: generated JSON and Python contracts reflect the new surface, the changelog and
public API reference are updated, and the package version is 0.6.0. Publishing remains a human step.

## Goal

Merge the Lesson Builder into the Textbook Agent as a polished, teacher-owned editing workspace by completing Phases 0-8 from the unified implementation guide.

## Current Phase

- Phase 0c - Version bump + publish prep
- Repo: `C:\Projects\lectio`
- Status: complete

## Phase 0a Checklist

- [x] Read Phase 0a requirements from the unified implementation guide
- [x] Confirm current Lectio exports/registry state
- [x] Add `src/lib/runtime/LectioBlockRuntimeSurface.svelte`
- [x] Add `src/lib/runtime/index.ts`
- [x] Add `src/lib/lectio/registry/render-map.ts`
- [x] Export runtime surface from `src/lib/index.ts`
- [x] Add/adjust tests for known-component rendering and unknown-component fallback
- [x] Run validation: `npm run check && npm run build && npm test`
- [x] Self-review diff for scope and compatibility
- [ ] Commit with convention-compliant message

## Validation Plan

- `npm run check`
- `npm run build`
- `npm test`

## Dependencies

- Guide Part A decisions (single source of truth + Lectio remains package boundary)
- Existing component registry and component exports

## Validation Evidence

- `npm run check` passed (`svelte-check found 0 errors and 0 warnings`)
- `npm run build` passed (vite build completed)
- `npm test` passed on rerun (`15 passed`, `88 passed`)
- Added focused phase test: `src/test/block-runtime-surface.test.ts`

## What Was Done

- Added a registry-driven render map keyed by component IDs:
  - `src/lib/lectio/registry/render-map.ts`
- Added the runtime block surface:
  - `src/lib/runtime/LectioBlockRuntimeSurface.svelte`
  - `src/lib/runtime/index.ts`
- Exported runtime surface from root package:
  - `src/lib/index.ts`
- Added tests for:
  - Coverage of every registry component ID in the render map
  - Known component render path
  - Unknown component fallback behavior

## Next Phase Needs

- Phase 0b: add `teachingIntent` metadata and `PALETTE_GROUPS` exports.

---

## Phase 0b Checklist

- [x] Add `TeachingIntent` type to public metadata contracts
- [x] Add `teachingIntent` to every component `metadata.ts`
- [x] Add `getComponentsByIntent()` helper
- [x] Add `src/lib/lectio/registry/palette-groups.ts`
- [x] Export `TeachingIntent`, `getComponentsByIntent`, and `PALETTE_GROUPS`
- [x] Add tests for intent mapping and palette-group coverage
- [x] Run validation: `npm run check && npm run build && npm test`
- [x] Self-review diff for scope and compatibility
- [ ] Commit with convention-compliant message

## Phase 0b Validation Evidence

- `npm run check` passed (`svelte-check found 0 errors and 0 warnings`)
- `npm run build` passed (vite build completed)
- `npm test` passed (`16 passed` files, `91 passed` tests)
- Added focused test: `src/lib/schema/teaching-intent.test.ts`

## Phase 0b What Was Done

- Added `TeachingIntent` union and surfaced it through public exports.
- Added `teachingIntent` metadata to all 32 component metadata modules.
- Added helper and group exports:
  - `getComponentsByIntent(intent)`
  - `PALETTE_GROUPS`
  - `PaletteGroup` type
- Added `src/lib/lectio/registry/palette-groups.ts`.

## Next Phase Needs

- Phase 0c: version bump + publish prep and frontend dependency alignment.

---

## Phase 0c Checklist

- [x] Bump Lectio package version
- [x] Keep phase scope tight (version + dependency alignment only)
- [x] Validate frontend compatibility with updated Lectio package
- [x] Run frontend validation: `npm run check && npm run build`
- [x] Self-review change scope
- [ ] Commit with convention-compliant message

## Phase 0c Validation Evidence

- Lectio version updated from `0.4.4` to `0.4.5` in `package.json`
- Frontend dependency updated to `lectio: \"0.4.5\"`
- Frontend local install for validation resolved `node_modules/lectio` at version `0.4.5`
- Frontend `npm run check` passed
- Frontend `npm run build` passed

## Phase 0c What Was Done

- Updated Lectio package version for release prep (`0.4.5`).
- Aligned Textbook Agent frontend dependency target to `0.4.5`.
- Verified compatibility by installing from local Lectio source and running frontend checks/build.

## Next Phase Needs

- Phase 1: move builder module into Textbook Agent frontend.

---

## Xplore 0.6.0 Checklist

- [x] Add optional quiz-option diagnostic metadata
- [x] Add optional section concept-card provenance
- [x] Add the diagnostic AnswerKey component and runtime/editor/print integration
- [x] Export JSON and Python contracts and prepare version 0.6.0
- [x] Fix SSR-safe markdown and SVG sanitization discovered during browser validation
- [x] Pass tests, checks, package validation, production build, and port-5173 smoke checks

## Xplore 0.6.0 Validation Evidence

- `pnpm test`: 19 files, 112 tests passed
- `pnpm run check`: 0 errors; 2 pre-existing CalloutBlock warnings
- `pnpm run package`: passed with the existing `@sveltejs/kit` dependency declaration warning
- `pnpm run build`: passed with existing selector and bundle-size warnings
- Browser smoke: `/`, `/components#answer-key`, `/templates`, and `/docs/contracts` returned
  HTTP 200 from `127.0.0.1:5173`

## Next Phase Needs

- Publish or locally link Lectio 0.6.0 through the repository owner's release process before
  beginning the downstream text-book-generator work.
