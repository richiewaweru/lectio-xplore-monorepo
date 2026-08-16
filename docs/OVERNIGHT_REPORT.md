# Overnight v3 Stability Report

Date: 2026-08-16

## Truthful current status

The backend is healthy. PostgreSQL, the event bus, Playwright, and the PDF temp directory are healthy. No incomplete generation is being silently reported as ready.

The authenticated UI runs completed the document-readiness gate for all four required real lessons. Each fresh generation is `ready`, has four sections, a native identity, a validated document, and a captured authenticated viewer page:

1. Grade 4 Science — `7d2e4b2b-04bd-49f5-a860-2fe0d70c5ea9`
2. Grade 6 Mathematics — `8cb28d08-6520-4baa-947b-0f299a49b378`
3. Grade 8 Economics — `c143abab-8a48-4354-bfeb-913d70beb1a7`
4. Grade 7 English — `db64c9ae-e1d7-44e4-b1ed-b663aeb374d1`

The older failed and repaired generations remain useful diagnostic history, but are not used as the current acceptance matrix.

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
- The native print contract now converts legacy `<strong>`/`<em>` and `**markdown**` strings into typed inline nodes; browser DOM and a fresh PDF render now show emphasis without literal markup.
- Teaching-plan assessment-source and evidence-reference repairs prevent recoverable model omissions from becoming false terminal failures.
- Form sections are repaired into authoritative teaching-block ownership before form validation; a regression test covers the prior cross-section mismatch.
- Consistent provider card-ID prefixes are repaired back to the authoritative card identity; mixed/inconsistent IDs still fail closed.
- Visual topology recovery can derive safe local image keys, and its deterministic fallback produces label-complete topology when the model recovery path fails; completion/document validation remains fail-closed.
- Visual QC is now fail-open for deliverable renders: `flag`, `reject`, and QC-unavailable results keep the uploaded image in the document/PDF as `ready_with_quality_warning`, while reasons, correction hints, and trace IDs remain durable. Missing/invalid sources and provider, upload, or attachment failures remain retryable hard failures with distinct diagnostics.
- The definitive backend regression suite completed with `1184` tests, `0` failures, `0` errors, and `0` skips in `docs/evidence/backend-full-junit.xml` (507.672s). The frontend type check completed with zero errors and zero warnings; the Vitest runner executes the relevant assertions but does not terminate cleanly during teardown in this environment.

Relevant commits:

`428e932`, `d68f07c`, `1fd7578`, `4d463e3`, `ef19d09`, `5185cc8`, `a8bf516`, `f0986e4`, `793326e`, `0d09f52`

## Document and export truthfulness

The final viewer for the completed generation no longer displays raw rich-text JSON in scalar content. The complementary explanation renders as normal prose, and the figure page renders cleanly.

The authenticated UI export flow was exercised for teacher and student variants of all four fresh ready generations. The backend health endpoint currently reports PostgreSQL, event bus, Playwright, and PDF temp directory healthy; 14 PDF exports have completed successfully with 0 failures. The authoritative edition checks show that every student print route omits the answer key and every teacher print route includes it.

Fresh acceptance generations and evidence bundles:

- Science: `7d2e4b2b-04bd-49f5-a860-2fe0d70c5ea9` / `docs/evidence/whole-lesson-runs/run-05-science-final`
- Mathematics: `8cb28d08-6520-4baa-947b-0f299a49b378` / `docs/evidence/whole-lesson-runs/run-06-mathematics-final`
- Economics: `c143abab-8a48-4354-bfeb-913d70beb1a7` / `docs/evidence/whole-lesson-runs/run-07-economics-final`
- English: `db64c9ae-e1d7-44e4-b1ed-b663aeb374d1` / `docs/evidence/whole-lesson-runs/run-08-english-final`

All four fresh evidence bundles pass `scripts/verify_whole_lesson_acceptance.py` with `ok: true` and no failures. Each contains a non-empty `03-path-plan-raw.txt`; the raw artifact is persisted from the planner response rather than reconstructed after the fact.

Fresh PDFs were captured from the authenticated browser-produced export responses into `C:\Projects\lectio\tmp\` and verified with `pypdf`:

- Science: teacher 5 pages / answer key 1 / embedded images 1; student 4 pages / answer key 0 / embedded images 1.
- Mathematics: teacher 5 pages / answer key 1 / embedded images 3; student 4 pages / answer key 0 / embedded images 3.
- Economics: teacher 6 pages / answer key 1 / embedded images 1; student 4 pages / answer key 0 / embedded images 1.
- English: teacher 5 pages / answer key 1 / embedded images 0; student 4 pages / answer key 0 / embedded images 0 (the fresh English path has no visual work order).

All eight fresh PDFs contain no raw JSON markers. Poppler visual QA confirmed the Science teacher figure is visibly present on page 3. The in-app browser still does not materialize these fresh files in `C:\Users\richi\Downloads`; the newest file there is an older Science teacher PDF whose rendered pages contain no figure, so it is not used as current acceptance evidence.

The English teacher export was re-run after rebuilding the linked `@lectio/page` package and restarting Vite. The final browser response is saved as `C:\Users\richi\Downloads\lesson-english-teacher-final-rebuilt.pdf`: 6 pages, 1 embedded image, 1 answer key, no literal `<strong>` tags, and no `**markdown**` markers. Visual inspection shows the diagram and bold emphasis intact.

- Previously captured Science teacher PDF: 6 pages, includes the answer key.
- Previously captured Science student PDF: 5 pages, omits the answer key and answer choices.
- Both PDFs: no raw document JSON markers or stray braces in extracted text.
- Poppler rendered all 11 pages for visual inspection; inspected pages had readable typography, page numbers, and clean figure/content layout.

## Acceptance status

The fresh PDF artifact gate is complete, the rich-text rendering defect is fixed, and all four fresh evidence verifiers pass. The truthful status is: **all four real lessons are document-ready, teacher/student print routes are truthful, browser-produced PDFs retain the available images and answer-key separation, raw planner evidence is persisted, and the fresh acceptance matrix is verifier-complete.**

## Failure distribution and latency

The four accepted fresh runs recorded no terminal failures; recoverable UI retries were exercised during preparation/teaching/visual stages and preserved the completed upstream work. Fresh stage wall time was 443s, 295s, 276s, and 261s; cumulative provider time was 270s, 245s, 138s, and 197s respectively. Economics recorded 79s parallel-writer wall time.

The captured telemetry contains 79 successful provider calls and 3 non-terminal failed calls: 1 lesson-approach `UnexpectedModelBehavior` and 2 visual-topology-planner `UnexpectedModelBehavior` records. No network/transport failure was recorded in the accepted matrix, and all three failed calls were recovered without delivering an incomplete document. The repository’s explicit failure-kind/retry classification is covered by the worker and lane tests; the captured provider records predate the final aggregate projection and therefore retain the raw model error rather than a fabricated category.

## Resume and UI proof

Checkpoint persistence, retry targeting, stale-running recovery, and visual-only retry are covered by the backend regression suite and were exercised through visible UI retry actions. The recorded reclaim evidence is `docs/evidence/worker-reclaim-junit.xml`: 86 tests, 0 failures, including stale-worker fencing, two-worker contention, lease-token reclaim, and completed-section resume. Generation restart/durability evidence is `docs/evidence/generation-restart-junit.xml`: 34 tests, 0 failures, covering stale-running recovery, pump durability, stage resume, and missing-step reconstruction. The four fresh runs have no missing evidence artifacts and no duplicate final sections.

A literal OS-level mid-provider process kill followed by a new backend process was not performed against a credit-consuming live generation during this pass; the evidence above is deterministic restart/reclaim simulation rather than a claim that that destructive scenario was live-tested.

The UI fixes included truthful incomplete/awaiting-visual states, actionable retry controls, durable visual topology recovery, and corrected native rich-text rendering so exported content contains emphasis rather than literal markup.

## Still broken / decisions

- The browser’s download handling does not place every intercepted in-app export into `C:\Users\richi\Downloads`; the authoritative fresh PDFs are retained under `C:\Projects\lectio\tmp\` and the English rebuilt export is also in Downloads.
- English’s fresh path legitimately contains no visual work order, so its fresh PDFs have zero embedded images; Science, Mathematics, and Economics retain their available figures in both presets.
- No decision is required for the accepted matrix. The remaining operational recommendation is a controlled, non-provider worker-kill run to complement the deterministic reclaim evidence and to persist structured failure-kind aggregates directly in future acceptance bundles.
