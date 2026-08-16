# Overnight v3 Stability Report

Date: 2026-08-16

## Truthful current status

The backend is healthy. PostgreSQL, the event bus, Playwright, and the PDF temp directory are healthy. No incomplete generation is being silently reported as ready.

The authenticated UI runs have completed the document-readiness gate for all four required real lessons:

- Generation: `046cdd0f-45bd-42e1-af3d-34fc91fc62bb`
- Topic: Grade 4 Science — Why Plants Need Light
- Persisted status/stage: `ready` / `ready`
- Persisted sections: 4
- UI path: prepare lesson, approve teaching plan, retry failed generation blocks, retry visual QC, then open the final viewer

Each `ready` state below is truthful for the persisted V2 document and authenticated viewer. PDF edition checks and saved artifact bookkeeping remain part of the final acceptance evidence.

1. Grade 6 Mathematics — Equivalent Fractions — generation `6693c7bf-8b2f-409a-906d-9f542ec59b15` is `ready` with a validated V2 document, four sections, rendered figures, and a working final-PDF action.
2. Grade 8 Economics — How Supply and Demand Affect Price — original generation `516aa260-13c1-4841-9484-6b67a1fb14e8` terminally failed with `no legal form candidates for blocks: ['check-b1']`; fresh generation `442c8a5f-16f9-4140-ac3b-9230424ac159` is now `ready` with a validated V2 document, four sections, and a completed visual retry.
3. Grade 7 English — Distinguishing a Claim from Supporting Evidence — generation `61fafb8b-2d34-49b5-9a81-f0c3dcba9b7f` is `ready` with a validated V2 document, four sections, and a rendered figure. The earlier generation `7dfa7b17-1516-41f7-9c36-fb54b2abae6a` did terminally fail on the item `card_id` mismatch.
4. Grade 4 Science — Why Plants Need Light — generation `046cdd0f-45bd-42e1-af3d-34fc91fc62bb` is `ready` with a validated V2 document, four sections, and a repaired visual handoff. A stale visual-dispatch marker had made print incorrectly unavailable; the authenticated retry cleared it and the viewer now permits export.

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
- Consistent provider card-ID prefixes are repaired back to the authoritative card identity; mixed/inconsistent IDs still fail closed.
- Visual topology recovery can derive safe local image keys, and its deterministic fallback produces label-complete topology when the model recovery path fails; completion/document validation remains fail-closed.

Relevant commits:

`428e932`, `d68f07c`, `1fd7578`, `4d463e3`, `ef19d09`, `5185cc8` (plus current uncommitted planning/schema fixes)

## Document and export truthfulness

The final viewer for the completed generation no longer displays raw rich-text JSON in scalar content. The complementary explanation renders as normal prose, and the figure page renders cleanly.

The authenticated UI export flow was exercised for teacher and student variants of all four ready generations. The prior process reported 4 successful exports and 0 failures; process-local counters reset after restart, so that telemetry is not treated as persisted evidence. The authoritative edition checks show that every student print route omits the answer key and every teacher print route includes it. The current print route also reports the required Science figure loaded at 1024x1056. However, the in-app browser did not create a fresh local PDF in `C:\Users\richi\Downloads` after the latest UI export attempts; the newest file there is an older Science teacher PDF and its rendered pages contain no figure. It is not used as current acceptance evidence.

- Previously captured Science teacher PDF: 6 pages, includes the answer key.
- Previously captured Science student PDF: 5 pages, omits the answer key and answer choices.
- Both PDFs: no raw document JSON markers or stray braces in extracted text.
- Poppler rendered all 11 pages for visual inspection; inspected pages had readable typography, page numbers, and clean figure/content layout.

## Remaining acceptance work

The remaining evidence task is to capture fresh local teacher/student PDF files from the in-app browser (or resolve its download handoff) and run the final repository evidence verifier. The honest current project status is **all four real lessons are document-ready, their teacher/student print routes are truthful, and the live print route contains its figure; PDF file evidence is not yet complete because the in-app browser is not placing the fresh blob downloads in `C:\Users\richi\Downloads`**.
