# Overnight v3 Stability Report

Date: 2026-08-15

## Truthful current status

The backend is healthy. PostgreSQL, the event bus, Playwright, and the PDF temp directory are healthy. No incomplete generation is being silently reported as ready.

The authenticated UI run completed for one real lesson:

- Generation: `046cdd0f-45bd-42e1-af3d-34fc91fc62bb`
- Topic: Grade 4 Science — Why Plants Need Light
- Persisted status/stage: `ready` / `ready`
- Persisted sections: 4
- UI path: prepare lesson, approve teaching plan, retry failed generation blocks, retry visual QC, then open the final viewer

This `ready` state is truthful for that generation. It must not be read as proof that the full four-lesson acceptance matrix is complete. The remaining required lessons have not yet been run and accepted:

1. Grade 6 Mathematics — Equivalent Fractions — generation `6693c7bf-8b2f-409a-906d-9f542ec59b15`, currently `awaiting_visuals`; visual retries continue to fail, so it is not accepted.
2. Grade 8 Economics — How Supply and Demand Affect Price — original generation `516aa260-13c1-4841-9484-6b67a1fb14e8` terminally failed with `no legal form candidates for blocks: ['check-b1']`; fresh generation `442c8a5f-16f9-4140-ac3b-9230424ac159` reached `awaiting_visuals`, but visual dispatch still fails. It is not accepted.
3. Grade 7 English — Distinguishing a Claim from Supporting Evidence — fresh generation `7dfa7b17-1516-41f7-9c36-fb54b2abae6a` terminally failed on an item `card_id` mismatch. It is not accepted.

## Reliability changes verified

- Stale `awaiting_visuals` records no longer appear as actively running, and polling stops when visual review is pending.
- Fresh preparation does not reuse an empty pre-worker `awaiting_visuals` record.
- Item execution has an explicit 90-second provider timeout and bounded retry policy.
- DeepSeek requests explicitly disable thinking when the configured reasoning policy is off; this removed the long-running reasoning behavior observed in the item executor.
- Planning nodes now explicitly disable provider reasoning for constrained JSON outputs.
- Same-user/unit path planning is serialized and idempotent against overlapping retries.
- `AnchorUsage` now explicitly accepts the active `contrast` slot.
- Failed section blocks and visual blocks can be retried without discarding blocks that already succeeded.
- Persisted/read/export document normalization unwraps rich-text values where scalar text is required.
- Teaching-plan assessment-source and evidence-reference repairs prevent recoverable model omissions from becoming false terminal failures.
- Form sections are repaired into authoritative teaching-block ownership before form validation; a regression test covers the prior cross-section mismatch.

Relevant commits:

`428e932`, `d68f07c`, `1fd7578`, `4d463e3`, `ef19d09`, `5185cc8` (plus current uncommitted planning/schema fixes)

## Document and export truthfulness

The final viewer for the completed generation no longer displays raw rich-text JSON in scalar content. The complementary explanation renders as normal prose, and the figure page renders cleanly.

The authenticated UI export flow was exercised for both variants before the latest backend restart. The prior process reported 4 successful exports and 0 failures; the current process-local counters reset to 0 after restart, so that telemetry is not treated as persisted evidence. The saved artifact checks after normalization show:

- Teacher PDF: 6 pages, includes the answer key.
- Student PDF: 5 pages, omits the answer key and answer choices.
- Both PDFs: no raw document JSON markers or stray braces in extracted text.
- Poppler rendered all 11 pages for visual inspection; inspected pages had readable typography, page numbers, and clean figure/content layout.

## Remaining acceptance work

Run and verify the remaining real lessons through the authenticated UI, resolve the English card-ID contract failure, and repeat the teacher/student export checks for every accepted generation. Until that is done, the honest overall project status is **partial — one of four real lessons accepted; Math and the fresh Economics run await visuals, and English is failed**.
