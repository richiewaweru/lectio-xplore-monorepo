# Handoff — Lesson document API and builder utilities (Proposal 1)

**Date:** 2026-03-28  
**Repo:** Lectio (`C:\Projects\lectio`)

---

## Handoff

**What changed**

- **Interchange and validation:** [`src/lib/document.ts`](../../../src/lib/document.ts) — `LessonDocument`, `BlockInstance`, `DocumentSection`, `fromSectionContents`, `toSectionContents`, `validateDocument`, `getFieldComponentMap`, related types.
- **Factories:** [`src/lib/content-factories.ts`](../../../src/lib/content-factories.ts) — `getEmptyContent`, `getPreviewContent`, `assertFactoriesCoverRegistry`.
- **Edit schemas:** [`src/lib/edit-schemas.ts`](../../../src/lib/edit-schemas.ts) — `getEditSchema`, `EditSchema` / field types.
- **Registry:** [`src/lib/registry.ts`](../../../src/lib/registry.ts) — `ComponentMeta` includes `teacherLabel`, `teacherDescription` (and exports used by builder/contracts).
- **Public API:** [`src/lib/index.ts`](../../../src/lib/index.ts) re-exports the builder-facing symbols consumers import from the `lectio` package.
- **Contracts export:** [`scripts/export-contracts.ts`](../../../scripts/export-contracts.ts) writes `teacher_label` and `teacher_description` per component into `agents/contracts/component-registry.json`.
- **Docs:** Reference for authors — [`docs/reference/lesson-document.md`](../../reference/lesson-document.md) (and related README links as present in this repo).

**Current state**

- Lesson Builder and Textbook Generator frontend depend on this package via `file:../lectio` (or published equivalent). Consumers should run a package build in this repo when `src/` changes.

**Validated**

- Run package checks/tests as defined in this repo’s `package.json` (e.g. `pnpm run check`, test script) after substantive edits.

**Not done yet**

- Keep `assertFactoriesCoverRegistry` / tests aligned when adding components.
- Run `npm run export-contracts` (or pnpm equivalent) after registry or template contract changes so downstream agents stay in sync.

**Start here**

- Barrel exports: [`src/lib/index.ts`](../../../src/lib/index.ts) (search for “Lesson document” section).
- Contract output: `agents/contracts/component-registry.json`.

**Risks**

- **Stale `dist/`:** Linked consumers may see old behavior until `pnpm package` (or build) refreshes build output.

---

## Downstream consumers

| Consumer | Role |
| --- | --- |
| `C:\Projects\lectio-lesson builder` | Imports `validateDocument`, `LessonDocument`, `getComponentById`, etc. |
| `C:\Projects\Textbook agent\frontend` | `lectio` for rendering + export mapping to `LessonDocument` |

---

## Cross-repo handoff

Orchestrator notes for the full three-repo slice: see **lectio-lesson-builder** `docs/project/runs/lesson-builder-cross-repo-handoff-2026-03-28.md`.
