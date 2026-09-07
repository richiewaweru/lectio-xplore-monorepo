# Library Runtime And Packaging Handoff

## Scope

This handoff covers both sets of March 19, 2026 library work:

- the already-authored packaging and contract-export expansion
- the uncommitted runtime-surface, template-expansion, simulation, and documentation changes

## What Changed

### 1. Library packaging and export contracts

- The package now ships from `src/lib` through `@sveltejs/package`.
- `src/lib/index.ts` exposes the public barrel surface for components, types, template helpers, presets, and validation utilities.
- `package.json` publishes `./theme.css` so consumers can import shared Lectio styling directly.
- `scripts/export-contracts.ts` now exports all 12 template contracts, the component field map, the full component registry, and the preset registry.
- `agents/contracts/` now contains the checked-in JSON snapshots consumed by downstream pipelines.

### 2. Public runtime surfaces for consumers

- Added `src/lib/theme.css` as the shared runtime stylesheet.
- Added `src/lib/templates/LectioThemeSurface.svelte` to scope preset-driven theme tokens.
- Added `src/lib/templates/TemplatePreviewSurface.svelte` for seeded previews by `templateId` and `presetId`.
- Added `src/lib/templates/TemplateRuntimeSurface.svelte` for real section rendering by `templateId`, `presetId`, and `section`.
- Added `src/lib/templates/ResolvedTemplatePreviewSurface.svelte` and `src/lib/templates/runtime-resolver.ts` to keep preview/runtime preset resolution consistent.
- Updated `src/app.css` so the app consumes the shared theme instead of duplicating it.
- Updated `src/lib/templates/TemplateDetailView.svelte` so the showcase preview runs through the same public surface that consumers use.

### 3. Template expansion and interactive support

- Added two new registry-backed templates:
  - `interactive-lab`
  - `guided-discovery`
- Added new template docs:
  - `src/lib/templates/interactive-lab/README.md`
  - `src/lib/templates/guided-discovery/README.md`
- Updated `src/lib/template-registry.ts` and contract export coverage so both templates are part of the library and JSON snapshots.
- Expanded `SimulationContent` with optional `html_content` in `src/lib/types.ts`.
- Updated `src/lib/components/lectio/SimulationBlock.svelte` to render iframe-backed live content, keep the fallback-diagram path, and support expanded modal viewing.
- Updated the dummy physics fixture to include a real HTML simulation payload for regression coverage.

### 4. Documentation and tests

- Updated `README.md` with current contract-export details and doc links.
- Updated `docs/reference/component-guide.md` to match the actual public library surface.
- Updated `docs/reference/registry-field-map.md` to cover the new preset registry and `--out` export flow.
- Added `src/test/runtime-surface.test.ts` for the new public preview/runtime wrappers.
- Updated existing tests to cover the 12-template registry, public preview flow, and live simulation behavior.

## Validation

- `npm run check` passed.
- `npm run test` passed with 4 files and 36 tests.
- `npm run build` passed.
- `npm run package` passed.
- `npm run export-contracts` passed.

## Known Follow-Up

- The production app build still emits a client chunk-size warning over 500 kB.
- Older internal template harness files still exist for showcase and regression coverage. Downstream consumers should use the registry plus the public runtime surfaces, not those harness files.
- Any future template, preset, registry, or export-surface change should be followed by:
  - `npm run package`
  - `npm run export-contracts`
  - a commit of the refreshed `agents/contracts/` snapshots

## Where To Start Next Time

- Start with `src/lib/index.ts` and `package.json` if the public package surface changes.
- Start with `src/lib/theme.css` and `src/lib/templates/LectioThemeSurface.svelte` if preset styling or shared runtime presentation changes.
- Start with `src/lib/templates/TemplatePreviewSurface.svelte` and `src/lib/templates/TemplateRuntimeSurface.svelte` if consumer rendering contracts change.
- Start with `src/lib/template-registry.ts` plus the template folder `README.md` files if templates are added, removed, or re-scoped.
- Start with `scripts/export-contracts.ts` and `agents/contracts/` if a downstream pipeline reports contract drift.
