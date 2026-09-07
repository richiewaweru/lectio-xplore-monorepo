# Feature: xplore Lectio 0.6.0 contract surface

**Classification**: major
**Subsystems**: types, component registry, runtime rendering, generated contracts, release metadata
**Branch**: `xplore`

## Source precedence

- `files (6).zip` supplies the corrected `MISSION.md` and `PROMPTS.md`.
- `files (5).zip` supplies `WORKED_EXAMPLE.md`, `LECTIO_XPLORE_HANDOFF.md`,
  `LECTIO_COMPONENT_SPEC.md`, `TBG_XPLORE_HANDOFF.md`, and `UI_SPEC.md`.
- The current component-owned architecture takes precedence over obsolete flat paths in the handoff.
- Lectio scope is phases L1–L4 only. Pack orchestration, generator prompts, and generator UI stay in
  the downstream text-book-generator repository.

## Progress

- [x] Understood requirements and identified scope
- [x] Read relevant source code and project rules
- [x] L1: add optional diagnostic metadata to quiz options
- [x] L2: add optional concept-card provenance to sections
- [x] L3: add and register the answer-key component
- [x] L4: export contracts and bump the package to 0.6.0
- [x] Run all tests, checks, package validation, and production build
- [x] Run a browser smoke check on port 5173
- [x] Self-review against `agents/standards/review.md`
- [x] Record final validation evidence and risks

## Validation evidence

- L1: diagnoses schema test — 1 passed.
- L1: `pnpm run build` — passed; existing CalloutBlock unused-selector and bundle-size warnings remain.
- L1: no learner-facing Svelte component references `diagnoses`.
- L2: `card_id` and `varies_on` are optional section-level metadata; production build passed and
  no renderer references either field.
- L3: answer-key/component integration suite — 28 passed.
- L3: `pnpm run check` — 0 errors; 2 pre-existing CalloutBlock unused-selector warnings.
- L3: `pnpm run build` and `pnpm run export-contracts` — passed.
- L3: no audience policy or literal color values were added; diagnostic wording and print break
  behavior match the component specification.
- L4: generated JSON and Python contracts contain `diagnoses`, `card_id`, `varies_on`, and
  `answer-key`; package version is 0.6.0.
- Release audit: the unified contract version is derived from `package.json` and exports as
  `0.6.0`; the export regression test compares the artifact and package versions.
- Final: `pnpm test` — 19 files and 112 tests passed.
- Final: `pnpm run check` — 0 errors; 2 pre-existing CalloutBlock unused-selector warnings.
- Final: `pnpm run package` and `pnpm run build` — passed.
- Browser: `/`, `/components#answer-key`, `/templates`, and `/docs/contracts` returned HTTP 200
  from `127.0.0.1:5173`; the AnswerKey registry entry was present in the rendered catalog.
- Self-review: no debug code, forbidden learner-facing diagnostic rendering, literal AnswerKey
  colors, or architecture-boundary violations found.

## Risks and follow-up

- npm publishing is authorized for this release, but requires an authenticated npm session.
- The downstream text-book-generator work consumes the published package after the release is
  available, with local contract sync used only for pre-publication validation.
- Packaging reports the existing `@sveltejs/kit` dependency declaration warning.
- The component catalog reports an existing nested-button hydration issue in `PrerequisiteStrip`;
  the page remains usable and the issue is outside the xplore contract/component scope.
- Existing CalloutBlock selector, bundle-size, and test `derived_inert` warnings remain.

## Bugfix: SSR markdown sanitizer

**Classification**: minor
**Root cause**: the browser-only DOMPurify default export has no `sanitize` method during SvelteKit
server rendering, so `/components` returned HTTP 500.

- [x] Reproduced the bug in a real browser on port 5173
- [x] Identified the server-only DOMPurify export mismatch
- [x] Switched to the isomorphic DOMPurify wrapper
- [x] Added Node-environment regression coverage
- [x] Re-ran validation and browser smoke test
- [x] Self-reviewed the focused diff
