# Cursor Run 06 — Frontend Render and A4 PDF

## Goal

Render the persisted application-generated v2 lesson and export it through the real application print path.

## Work

1. Add `@lectio/page` workspace dependency. Retain legacy `lectio`.
2. Add discriminated TypeScript API types.
3. Route v1 documents to legacy renderer and v2 documents to `LectioDocumentView`.
4. Apply teacher/student visibility policy in Xplore before passing document to Lectio.
5. Reuse the maintained print route and readiness signal found in Run 00.
6. Ensure frontend does not reorder blocks.
7. Add screen tests for all first-slice objects and figure states.
8. Add browser test that opens persisted v2 fixture through application route.
9. Generate A4 PDF through existing backend export or application Playwright pipeline.
10. Record PDF, page count, DOM block IDs, and overflow scan evidence.

## Gate

Application-generated lesson renders after reload and prints to A4. Section title appears once. Both v1 and v2 viewer tests pass.

## Commit

`feat(frontend): render and print lectio v2 documents`
