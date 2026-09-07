# Decision Log

## Phase 0a - LectioBlockRuntimeSurface

### Decision: Build render map from registry keys, not a hardcoded component-id map
- **Context:** `C:\Projects\lectio-lesson builder\src\lib\components\canvas\BlockPreview.svelte` uses a large manual component map keyed by `component_id`, which can drift when new components are added.
- **Guide says:** Add a registry-driven runtime block renderer and eliminate manual component maps.
- **Chose:** Added `src/lib/lectio/registry/render-map.ts` that derives `componentRenderMap` from `componentRegistry` keys (`registryKey -> metadata.id`) plus public `components/lectio` exports. Missing mappings throw early.
- **Risk:** This depends on `componentRegistry` keys matching `components/lectio` export names. Mitigation: startup throw on mismatch and test coverage in `src/test/block-runtime-surface.test.ts`.

## Phase 0b - Teaching intent + palette groups

### Decision: Treat `glossary-inline` as `define` intent but keep it out of palette groups
- **Context:** The guide's mapping table covers section-backed block components and does not explicitly include `glossary-inline` (inline-only component with `sectionField: null`).
- **Guide says:** Add `teachingIntent` to every component metadata file and expose grouped palette exports.
- **Chose:** Assigned `glossary-inline` intent as `define` for metadata completeness, and built `PALETTE_GROUPS` from section-backed components only (`sectionField !== null`) so inline components are not offered as addable blocks.
- **Risk:** If a future builder wants inline-component insertion directly, palette filtering rules must be revisited. Current behavior matches the block-based workspace model.

## Phase 0c - Version bump and frontend alignment

### Decision: Use local Lectio install for frontend validation before publish
- **Context:** `npm version patch --no-git-tag-version` in Lectio triggered repo hooks (`version`/`postversion`) and attempted `git push`, which failed due no upstream on the phase branch. Also, `0.4.5` is not yet published to npm in this local workflow.
- **Guide says:** Publish a new Lectio version and update frontend dependency, then verify frontend build/check.
- **Chose:** Kept the Lectio version bump (`0.4.5`), updated frontend dependency target to `0.4.5`, and validated compatibility by installing frontend from local `C:\\Projects\\lectio` source with `--no-save --no-package-lock` before running frontend `check` and `build`.
- **Risk:** Lockfile alignment with registry-published `0.4.5` is deferred until publish is performed. Validation still proves code compatibility against the updated package contents.
