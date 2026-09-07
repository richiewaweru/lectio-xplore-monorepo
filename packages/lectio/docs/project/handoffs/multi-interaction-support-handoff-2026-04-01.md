# Multi-Interaction Support Handoff

## What Changed

Lectio now supports multiple interactions per section through `SectionContent.simulations?: SimulationContent[]`, while still reading the legacy singular `simulation?: SimulationContent` during migration. The runtime now normalizes both shapes through `getSectionSimulations()`, so templates, validation, and document round-trips all treat plural simulations as the canonical path.

Diagram content also now supports `image_url?: string` in addition to inline SVG. `DiagramBlock` prefers `image_url` when present, but keeps zoom/callout behaviour for SVG-backed diagrams.

## Core Files

| File | Change |
|---|---|
| `src/lib/types.ts` | Added `simulations?: SimulationContent[]`, kept legacy `simulation?: SimulationContent`, added `DiagramContent.image_url?: string` |
| `src/lib/section-content.ts` | New normalization helper for plural/singular simulation reads |
| `src/lib/document.ts` | Emits repeated `simulation-block`s from `simulations[]` and rebuilds repeated blocks back into `simulations[]` |
| `src/lib/validate.ts` | Validates every normalized simulation and allows image-backed diagrams without requiring SVG |
| `src/lib/registry.ts` | Maps `simulation-block` to `simulations` and removes the misleading single-instance capacity hint |
| `src/lib/template-validation.ts` | Treats `simulations` as an array-backed preview field |
| `src/lib/components/lectio/DiagramBlock.svelte` | Renders `image_url` when present and limits callouts to SVG-backed diagrams |
| `src/lib/templates/*/layout.svelte` | High-interaction templates now loop over normalized simulations |
| `src/lib/templates/*/config.ts` | Raised `simulation-block` budgets to `2` where intended |
| `src/lib/dummy-content.ts` and template previews | Migrated repo-owned examples to `simulations: [...]` |
| `src/test/lectio.test.ts` and `src/lib/document.test.ts` | Added regression coverage for plural simulations, legacy fallback, and image-backed diagrams |

## Contracts And Docs

- Regenerated contract exports in `agents/contracts/`
- Updated `README.md`
- Updated `docs/reference/registry-field-map.md`
- Updated the earlier registry handoff note so it no longer claims `simulation-block` maps to singular `simulation`

## Verification

- `npm run export-contracts`
- `npm run test`
- `npm run check`
- `npm run build`

All four pass on the current branch after this change set.

## Important Migration Notes

- Internal repo examples, previews, validation paths, and document rebuilds now prefer `simulations`.
- Legacy singular `simulation` is still supported for reads during migration.
- Document rebuilds normalize repeated `simulation-block`s into `simulations[]`; they do not write back the legacy singular field.
- `DiagramBlock` supports both `svg_content` and `image_url`, but callout overlays only make sense for SVG-backed diagrams.

## Test Infrastructure Note

Vitest was updated to exclude `.claude/**` so stale scratch worktrees do not get swept into the main project test run. That was causing duplicate old copies of the app to fail against the new plural simulation contract.
