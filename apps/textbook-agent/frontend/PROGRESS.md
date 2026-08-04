# Builder Repairs Progress

Goal: Fix all builder usability bugs across 5 ordered PRs, verifying each PR before moving to the next.

## PR 1: Critical Interaction Fixes

**Classification**: minor
**Root cause**: block-card keyboard handling intercepted editing keystrokes; the canvas had no bottom section insertion point; the add-block control scrolled away; preview containers allowed long content to escape.

### Progress
- [x] Identified root cause
- [x] Implemented the fix
- [x] Added or updated regression coverage where practical
- [x] Ran validation
- [x] Self-reviewed the diff

### Verification Checklist
- [x] Spacebar works in all text fields during editing
- [x] Enter on a non-editing selected block still opens edit mode
- [x] New sections appear below existing content
- [x] "Add block" button stays visible while scrolling
- [x] Preview text wraps and doesn't overflow
- [x] Ctrl+P prints clean (no sticky bar, no builder chrome)
- [x] npm run check passes
- [x] npm run build passes

### Validation Evidence
- `npm run check` passed: svelte-check found 0 errors and 0 warnings.
- `npm run build` passed.
- Automated component regression coverage was not added for PR 1 because the affected behavior is DOM keyboard/scroll/print styling in builder Svelte components; validation is by code path review plus check/build.

### Risks
- Low. Changes are local to builder canvas/shell behavior and CSS containment.

## PR 2: Edit Schema Fixes - Tables and Definitions

**Classification**: minor
**Root cause**: several builder-facing Lectio edit schemas exposed only top-level fields while omitting the nested arrays that teachers need to edit real content.

### Progress
- [x] Identified root cause
- [x] Implemented the fix
- [x] Added regression tests
- [x] Ran validation
- [x] Self-reviewed the diff

### Verification Checklist
- [x] Comparison grid: can add/edit columns and rows in the editor
- [x] Comparison grid: empty block starts with 2 columns and 1 row scaffold
- [x] Comparison grid: existing AI-generated grids still render (backward compat)
- [x] Definition family: can add/edit definition entries
- [x] Definition family: empty block starts with one empty definition
- [x] Fill-in-blank: improved labels are clear
- [x] Fill-in-blank: word bank field is available
- [x] Fill-in-blank: empty block has a pre-filled example segment
- [x] npm run check passes
- [x] npm run build passes
- [x] npm test passes

### Validation Evidence
- Lectio `npm run test` passed: 14 files / 88 tests.
- Lectio `npm run check` passed: svelte-check found 0 errors and 0 warnings.
- Lectio `npm run build` passed.

### Risks
- Low to medium. `comparison-grid` now accepts both legacy string cell values and builder object-list cell values; validation and rendering normalize both shapes.

## PR 3: Diagram Media Support

**Classification**: minor
**Root cause**: diagram edit schemas and renderers only supported SVG/text URL fields, so uploaded media from the builder media picker could not drive diagram previews.

### Progress
- [x] Identified root cause
- [x] Implemented the fix
- [x] Added regression tests
- [x] Ran validation
- [x] Self-reviewed the diff

### Verification Checklist
- [x] Diagram block: media picker field appears in editor
- [x] Diagram block: uploaded image renders in preview
- [x] Diagram block: image_url still works as fallback
- [x] Diagram block: SVG still works as fallback
- [x] Diagram block: width control works
- [x] Existing AI-generated diagrams still render (backward compat)
- [x] npm run check passes
- [x] npm run build passes
- [x] npm test passes

### Validation Evidence
- Lectio `npm run test` passed: 14 files / 93 tests.
- Lectio `npm run check` passed: svelte-check found 0 errors and 0 warnings.
- Lectio `npm run build` passed.

### Risks
- Low. Media ID support is priority-based and preserves existing `image_url` and SVG fallback paths.

## PR 4: Open in Builder on Dashboard

**Classification**: minor
**Root cause**: the generation detail route could convert completed V3 documents into builder lessons, but the dashboard V3 history list only exposed the viewer link.

### Progress
- [x] Identified root cause
- [x] Implemented the fix
- [x] Added regression tests
- [x] Ran validation
- [x] Self-reviewed the diff

### Verification Checklist
- [x] Dashboard shows "Edit in Builder" on completed V3 generations
- [x] Clicking it creates a builder lesson and navigates to /builder/{id}
- [x] Non-completed generations don't show the button
- [x] Builder opens with correct blocks from the generation
- [x] npm run check passes
- [x] npm run build passes

### Validation Evidence
- Frontend `npm run test -- src/routes/dashboard/page.test.ts` passed: 4 tests.
- Frontend `npm run check` passed: svelte-check found 0 errors and 0 warnings.
- Frontend `npm run build` passed.

### Risks
- Low. The dashboard reuses the existing V3 pack-to-builder adapter and builder lesson API.

## PR 5: Palette Speed + Page Warnings

**Classification**: minor
**Root cause**: palette insertions kept the overlay open through block creation/edit handoff, making the interaction feel slow; the builder also had no lightweight page estimate before print/export.

### Progress
- [x] Identified root cause
- [x] Implemented the fix
- [x] Added regression tests
- [x] Ran validation
- [x] Self-reviewed the diff

### Verification Checklist
- [x] Palette closes before inserting a block
- [x] Newly inserted palette blocks are selected and scrolled into view
- [x] Sticky add-block bar remains available for fast insertion
- [x] Toolbar shows estimated A4 page count
- [x] Page count warning escalates for longer documents
- [x] npm run check passes
- [x] npm run build passes
- [x] npm test passes

### Validation Evidence
- Frontend `npm run test -- src/lib/builder/utils/page-estimate.test.ts src/lib/builder/components/toolbar/DocumentToolbar.test.ts src/routes/dashboard/page.test.ts` passed: 3 files / 10 tests.
- Frontend `npm run check` passed: svelte-check found 0 errors and 0 warnings.
- Frontend `npm run build` passed.
- Frontend full `npm run test` passed: 55 files / 191 tests.

### Risks
- Low. Page counts are estimates by design, and palette insertion keeps the existing fallback behavior when no custom add handler is provided.

## Final Stopping Condition

- [x] PR 1: Spacebar works in edit fields
- [x] PR 1: New sections insert below existing content
- [x] PR 1: "Add block" button sticks while scrolling
- [x] PR 1: Preview text doesn't overflow block boundaries
- [x] PR 2: Comparison grid has full column/row editing
- [x] PR 2: Definition family has definition entry editing
- [x] PR 2: Fill-in-blank has improved labels and word bank
- [x] PR 3: Diagram blocks accept images via media picker
- [x] PR 3: Existing diagrams still render (backward compat)
- [x] PR 4: Dashboard has "Edit in Builder" on completed generations
- [x] PR 5: Palette insertion is fast (close-first pattern)
- [x] PR 5: Page count shows in toolbar with warnings
- [x] All npm run check / build / test pass in both repos
