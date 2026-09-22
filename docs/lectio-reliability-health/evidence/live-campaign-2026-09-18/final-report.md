# Core Lectio Lesson Flow Reliability Campaign — final report

Date: 2026-09-18  
Final verdict: **NOT VERIFIED**

## Executive result

The implementation repairs the identified Plan failure-state, polling,
retry/checkpoint, Print projection, legacy Teaching Plan normalization, and
realization identity defects. The authenticated live campaign now covers
teacher preparation through approval, Learn/Print realization, editing,
preview, publishing, assignment, learner join, server-side interaction
evaluation, refresh hydration, and completion for selected cases.

The campaign is not fully green. Case D Print remains queued with a pending
figure; the live controlled recoverable-failure sequence was not run; physical
PDF files were not exposed for visual inspection; and duplicate/forged learner
submission checks were not run in the browser. The phrase `CORE FLOW LIVE
VERIFIED` is intentionally not used.

## Repairs implemented

1. Plan status preserves structured backend error metadata and distinguishes
   recoverable, terminal, cancellation, approval, ready, and running states.
2. Known failures, including `execution_started=true` failures, cannot fall
   through to generic `working`; polling stops for every non-running state.
3. Native retry failure injection is placed at the intended writer boundary and
   remains bounded and test-controlled.
4. Selected-learner dependency overrides match the current authorization
   contract without weakening learner or assignment semantics.
5. Print retry resumes from the shared preparation checkpoint without creating
   a duplicate logical generation.
6. Legacy approved snapshots are normalized into a durable Teaching Plan
   revision; obsolete legacy `variant` keys are removed before v2 validation.
7. Learn and Print use their dedicated editor routes; live Learn save/reload
   persistence was verified.
8. Formative shared-response projection admits the exact mapped Print treatment
   without widening the closed candidate set.
9. Plan realization cards now treat queued/running/preparing rows as preparing,
   even when an output ID exists. A queued Print row therefore cannot render as
   falsely ready.

## Automated result

See [automated-gates.md](automated-gates.md).

- Frontend targeted regression: 6 passed.
- Frontend `pnpm check`: 0 errors, 5 existing warnings.
- Backend shared-plan/status projection tests: 30 passed, 1 warning.
- Previously recorded repository gates remain passing: frontend suite 275
  tests, focused backend reliability 51 tests, path/realization 21 tests,
  backend full suite 1462 passed, contracts, page, architecture, and domain
  guards.

## Live result by gate

| Gate | Result | Evidence |
|---|---|---|
| A sequence/cycle | PARTIAL | [case-a-live.md](case-a-live.md) |
| B classification | PASS WITH FOLLOW-UP | [case-b-live.md](case-b-live.md) |
| C mathematical procedure | PASS WITH FOLLOW-UP | [case-c-live.md](case-c-live.md) |
| D visual concept | BLOCKED | [case-d-live.md](case-d-live.md) |
| Teacher Learn/Print flow | PARTIAL | Learn creation/edit/save/reload/preview/publish/assignment passed in live cases; D Print is still queued. |
| Learner join/interaction/refresh/completion | PASS WITH FOLLOW-UP | B had two server-evaluated interactions and durable completion; C completed with no interaction nodes; A and D learner consumption remain outstanding. |
| Controlled recoverable failure | BLOCKED | Automated checkpoint/retry coverage passed; live failure → stopped polling → user retry → checkpoint resume was not run. |
| PDF content/layout inspection | BLOCKED | Export actions returned through the UI, but physical artifacts were unavailable for visual inspection. |

## Shared-plan integrity

The live Learn and Print admissions for Case B used Teaching Plan
`33570b12-43a7-46e4-b39d-eddb3000851a`, revision 1, hash
`dcaa5d04c03d592e0070e8bab323a2cd19f2f7da23161c1f5323c84d2a0fdd17`.
The learner release was published from the Learn realization and remained
stable through interaction, refresh, and completion. The unrelated Print issue
did not erase approval or learner state. Case A retains a legacy Print hash
difference and is recorded as provenance follow-up. Automated realization
isolation and idempotency coverage passed.

## Learner evidence

- Campaign class invite code and learner private details are redacted.
- Math instance `f027…` completed with all four sections persisted after
  refresh and no attempts because its document had no interaction nodes.
- Classification instance `e675…` completed after two correct practice
  submissions. Database state recorded exactly two attempt rows, six practice
  points, all required sections, and both interaction IDs. Refresh preserved
  `LEARNING INSTANCE · COMPLETED`.
- Forged-score rejection, duplicate submission, and duplicate logical work were
  not browser-tested in this campaign; the automated backend gates cover the
  relevant invariants.

## Remaining risks and unblock actions

1. Finish the queued visual Print realization with an authorized visual
   provider/model, then rerun D through PDF inspection and learner completion.
2. Run the live isolated recoverable failure with exact status sequence,
   polling cadence, Network/Console capture, and user retry.
3. Capture accessible teacher/student PDF artifacts and inspect clipping,
   tables, figures, spacing, answer leakage, and missing keys.
4. Run browser duplicate-submission and forged-score attempts and persist the
   redacted evidence.
5. Consume A and D learner assignments after their remaining teacher/Print
   gates are complete.

## Final verdict

`NOT VERIFIED`. The repairs are implemented and well-covered by automated
tests, and the authenticated live run materially reduced the uncertainty. The
mandatory visual Print, live failure-injection, PDF visual-QA, and some learner
integrity gates remain open, so claiming full live verification would be
incorrect.
