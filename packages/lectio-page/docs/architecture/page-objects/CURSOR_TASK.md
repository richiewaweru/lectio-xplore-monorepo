# Cursor Task — Lectio v2 Phase 1

**Scope: the new Lectio library only. Do not touch the backend, the textbook agent app, or any published package.**

This is a long autonomous run. Work through the phases in order. Commit once per phase. If a verify gate fails, stop and write the reason into `FINDINGS.md` rather than working around it.

---

## Inputs

- `artifacts/` — A through G, the architecture pack
- Repo-root `contracts/object-catalogue.v1.json`, `intent-catalogue.v1.json`, `lectio-document-v2.schema.json` (catalogues are not duplicated under this pack)
- Pack `contracts/base-print.css` — **use the v1.1 patched version**, not the one in the original pack
- `PATCH-v1.1.md` — four corrections, already applied to the CSS; FIX 1 also requires a schema edit
- `references/margin-test-2.html` — the proven page geometry, rendered and verified in Chromium
- `references/Photosynthesis_Booklet.docx` and `grade7_photosynthesis_3_lesson_booklet.pdf` — target quality
- `references/Lessons · Lectio.pdf` — the problem being solved

---

## Phase 1 — Repo scaffold

Fresh repo per artifact A. **Do not clone the existing Lectio and delete.** Carry only: build config, tsconfig, vitest setup, the contract-export script skeleton, `sanitize.ts`, `markdown.ts`.

Do not carry: any component, the registry, `component-meta.ts`, `field-map.ts`, `schema/types.ts`, `teacher/document.ts`, `content-factories.ts`, `edit-schemas.ts`, template configs, `print-theme.css`, `base-presets.ts`, `printContext.ts`.

**Gate.** `grep -ri "usePrintMode\|printMode\|BLOCK_FIELD_ORDER\|SectionContent\|component_id" src/` returns nothing. Build passes on an empty library.

---

## Phase 2 — Contracts and types

Apply FIX 1 to `lectio-document-v2.schema.json` (add `front_matter`). Generate TypeScript types from the schema. Wire `export-contracts` to emit the object catalogue, intent catalogue and document schema.

**Gate.** Types compile. `npm run export-contracts` produces all three files. A fixture document validates against the schema.

---

## Phase 3 — The ten page objects

Build to artifact D against the patched `base-print.css`. One Svelte component per object.

**Hard rules — refuse these:**
1. No `@media print` block anywhere. If an object needs stripping for print, it was built screen-first. Rebuild it.
2. No border or background on any object except Aside.
3. No object renders its own name, type, or intent as a visible label.
4. No `printMode` prop, context, or branch. One rendering only.
5. No colour carries meaning alone — this will be photocopied in black and white.
6. No millimetre value that depends on page geometry outside the CSS geometry block.
7. Heading is not standalone: it emits a `.lectio-heading-binding` wrapper around itself and the following block. `break-after: avoid` does not chain in Chromium.
8. Nothing load-bearing may depend on background rendering.

**Gate.** Ten components exist. `grep -rn "@media print" src/` returns nothing. `grep -rn "border\|background" src/` returns matches only in the Aside component.

---

## Phase 4 — Reference rebuild

Rebuild three pages of `Photosynthesis_Booklet.docx` as fixture data — a JSON document conforming to the v2 schema — and render it. Hand-authored content, no pipeline.

Render to PDF via Playwright at A4. Produce **two** PDFs: one with `print_background=True`, one with `False`. They must be visually identical.

**Gate.** Both PDFs render. They match. Page count is at or below the original booklet's for the same content. Write both to `out/`.

---

## Phase 5 — Screen layer

Thin wrapper adding decoration for on-screen review only. CSS only — no markup changes, no component branching.

**Gate.** Removing the screen stylesheet leaves the print output byte-identical.

---

## Report

Write `FINDINGS.md` covering:

- Did ten objects suffice, or was an eleventh needed? Which object resisted its assigned fields?
- Did Table genuinely absorb `definition_family`, `comparison_grid`, `insight_strip` and `timeline`? Timeline is the likeliest to resist.
- Any place a hard rule had to be bent, and why.
- Page count: rebuilt fixture vs the original booklet.
- Anything in artifacts A–G that turned out to be wrong.

---

## Out of scope — do not start

Backend rewiring. Prompt changes. Template re-expression as intents. QC routing. Publishing to npm. Migrating any saved document. The planner comparison in artifact C — that requires human judgment and is not an autonomous task.
