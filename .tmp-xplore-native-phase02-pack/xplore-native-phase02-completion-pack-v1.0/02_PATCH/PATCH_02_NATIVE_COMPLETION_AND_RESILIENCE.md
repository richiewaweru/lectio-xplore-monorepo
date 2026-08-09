# PATCH 02 — Native Completion and Resilience

## Goal

Make every native lesson that reaches teaching approval complete reliably through:

```text
approve → durable execution → form plan → block writers
→ DB-first assembly → persisted LectioDocumentV2
→ reload → teacher/student PDFs
```

## Baseline

- Branch: `pageobject-integration`
- Commit: `00cc3c7eea7c8d3bf5e56b4988f261e07aa247d6`

## Included

1. Canonical stage transitions.
2. Fast approval response.
3. DB-backed lease worker.
4. Form-plan resume.
5. Composite execution keys.
6. Skip-ready/retry-failed writers.
7. Bounded concurrency.
8. Failure isolation.
9. Structured retry and errors.
10. DB-first assembly.
11. Fresh-session reload.
12. Required-visual gate.
13. Native teacher/student PDF proof.
14. API/DB/log verification drivers.
15. Four official recorded runs.

## Excluded

Prompt tuning, complete skeleton guidance, item-budget expansion, Builder editing, new page objects, external queues, broad UI redesign, and historical v1 migration.

## Change 1 — Canonical transitions

Create one transition method that atomically updates canonical status, compatibility stage, heartbeat, event, and structured error. Add legal/illegal transition tests. Remove direct stage assignments from the Phase 02 path.

## Change 2 — Queue on approval

Refactor teaching approval to:

```text
validate revision → save approval → queued → return HTTP 202
```

Do not call the form planner or executor inline. Duplicate approval is idempotent.

## Change 3 — DB-leased worker

The worker atomically claims queued/stale jobs, persists worker ID/lease/heartbeat, owns its DB session, resumes from checkpoints, and releases at terminal state. FastAPI background tasks are insufficient.

## Change 4 — Form-plan resume

Reuse a persisted valid form plan. A restart after form planning must not call the form planner again.

## Change 5 — Composite block keys

Store block outcomes under:

```text
section_id:block_id:variant_id
```

Persist status, attempts, timestamps, object, intent, content, request ID, and structured error.

## Change 6 — Bounded concurrent writers

Run at most three writer calls concurrently. One failure returns a failed outcome and does not cancel siblings. Do not share one SQLAlchemy session concurrently.

## Change 7 — Resume policy

```text
ready/visual_pending → skip
failed retryable     → retry
missing              → execute
stale started        → retry
failed terminal      → leave failed
```

After the batch, retryable failures produce `failed_recoverable`; terminal failures produce `failed_terminal`. Do not assemble a final document with failure placeholders.

## Change 8 — Retry policy

Transport failures get up to three attempts with exponential backoff and jitter. Validation failures get one targeted repair. Keep prompt meaning unchanged.

## Change 9 — DB-first assembly

Reload the persisted form plan and every expected block outcome. Reject missing, failed, duplicate, unknown, object-mismatched, or intent-mismatched results. Reconstruct deterministic section/block order. Do not depend on the local writer list.

## Change 10 — Persist, reload, transition

Validate and persist `LectioDocumentV2`, commit, open a fresh DB session, reload and validate, then transition to `awaiting_visuals` or `ready`. Do not only assign `generation.status = completed`.

## Change 11 — Figure gate

Pending figures preserve block identity and stable request ID. Visual callbacks update the same block, bump revision, and recalculate remaining pending requirements. Final PDF is unavailable while required visuals are pending.

## Change 12 — Direct PDF verification

Call native PDF endpoints directly. Save teacher and student PDFs, verify nonzero page counts, extract text, confirm a known answer phrase appears only in the teacher PDF, and confirm no legacy pack conversion.

## Stop conditions

Stop and report if the page-object contract must change, safe claim needs an unplanned schema migration, native rendering is absent, the PDF service requires a major new subsystem, or question/visual source-of-truth semantics are unresolved.

## Success

Phase 02 completes only after a middle block fails once, siblings finish, backend restarts, stale work is reclaimed, ready blocks are skipped, failed work alone retries, assembly uses DB state, native reload succeeds, and teacher/student PDFs pass content assertions.
