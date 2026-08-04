# Handoff — Lesson Builder export (Proposal 2) and viewer UI

**Date:** 2026-03-28  
**Repo:** Textbook Generator (`C:\Projects\Textbook agent`)  
**Scope:** `frontend/` only for this slice (export + Lectio document view)

---

## Handoff

**What changed**

- **Portable export:** [`frontend/src/lib/generation/export-document.ts`](../../../frontend/src/lib/generation/export-document.ts) — builds a `LessonDocument` from a completed `GenerationDocument` and triggers browser download (e.g. `.lesson.json`).
- **Export control location:** **Export for Builder** lives in [`frontend/src/lib/components/LectioDocumentView.svelte`](../../../frontend/src/lib/components/LectioDocumentView.svelte), shown when `document.status === 'completed'` and the parent passes `onExportForBuilder`.
- **Wiring:** [`frontend/src/routes/textbook/[id]/+page.svelte`](../../../frontend/src/routes/textbook/[id]/+page.svelte) passes `onExportForBuilder` calling `exportToLessonDocument` + `downloadLessonDocument` (import from `export-document`). The page header no longer duplicates this button.

**Current state**

- Completed generations can export for import into the Lesson Builder app, provided Lectio types and export mapping stay aligned with `LessonDocument` version expectations.

**Validated**

- From `frontend/`: `pnpm run check`
- Component tests: `pnpm exec vitest run src/lib/components/LectioDocumentView.test.ts` (includes export button visibility + click behavior)

**Not done yet**

- End-to-end manual test: complete a generation → export → import in Lesson Builder → spot-check block rendering.
- If API shapes drift, update `export-document.ts` and any Zod/types in lockstep with Lectio.

**Start here**

- Export mapping: [`frontend/src/lib/generation/export-document.ts`](../../../frontend/src/lib/generation/export-document.ts)
- Viewer + button: [`frontend/src/lib/components/LectioDocumentView.svelte`](../../../frontend/src/lib/components/LectioDocumentView.svelte)

**Risks**

- **Lectio version skew:** `file:../../lectio` must match the Lesson Builder’s expected `LessonDocument` schema; coordinate bumps across three repos.

---

## Cross-repo handoff

Orchestrator notes: **lectio-lesson-builder** `docs/project/runs/lesson-builder-cross-repo-handoff-2026-03-28.md`.

Lectio API / contracts: **lectio** `docs/project/handoffs/lesson-document-builder-api-handoff-2026-03-28.md`.
