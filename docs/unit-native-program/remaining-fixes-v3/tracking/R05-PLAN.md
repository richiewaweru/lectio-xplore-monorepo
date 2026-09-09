# R05 Plan — Acceptance audit and handoff

## Before editing
- Full `tests/remaining_fixes` suite must be green on current worktree.
- Re-run affected P04/P06/P07/P08 and A04 authoring tests.
- Re-run R04 vitest component mounts.
- Fix any regression (Print lesson_title getattr) if still open.
- Audit GATES.csv: every row needs exact tested_commit SHA present in this round's history (not intermediate orphan SHAs, not vague HEAD).
- Correct v2 GATE_RESULTS for reopened A02/A04/A05/A06 using remaining-fixes evidence where clauses are now independently proven; leave non-proven clauses non-passing / deferred-note.
- Final report + STATE COMPLETE_OFFLINE; completion wording only if all 27 gates PASS.

## Completion wording target
`Remaining fixes verified offline; live/model-quality verification deferred`
