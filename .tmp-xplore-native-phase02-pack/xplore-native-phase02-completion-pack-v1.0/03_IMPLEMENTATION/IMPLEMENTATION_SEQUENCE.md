# Phase 02 Implementation Sequence

## Commit A — State and queue

Implement canonical transitions, execution metadata, HTTP 202 approval, atomic claim, heartbeat, stale reclaim, and idempotency.

Gate: approval returns promptly; duplicate approval creates one execution; two workers cannot both claim.

Suggested commit: `feat(native-execution): add durable queue and leased worker`

## Commit B — Resume and isolation

Implement composite keys, structured outcomes, skip-ready, retry failed/missing, max-three concurrency, and sibling completion.

Gate: a forced middle-block failure does not stop later blocks.

Suggested commit: `feat(native-execution): resume and isolate block failures`

## Commit C — DB-first assembly

Reload persisted form plan/outcomes, validate expected keys, assemble from DB, reload in a fresh session, and write authoritative terminal state.

Gate: restart before assembly and still complete correctly.

Suggested commit: `fix(native-execution): assemble from persisted block state`

## Commit D — Delivery proof

Verify direct native reload, pending-visual conflict, teacher projection, student projection, and PDF text assertions.

Gate: one conceptual lesson produces both correct PDFs.

Suggested commit: `feat(native-delivery): verify native teacher and student PDFs`

## Commit E — Four official runs

Freeze one commit. Run Science, Mathematics, Economics, and English. Do not tune prompts between them.

Suggested commit: `docs(evidence): record four native end-to-end lesson runs`

## Commit F — Legacy shutdown

Only after four runs pass, remove new-generation invocation of `resume_stage2` and silent fallback, retain read-only v1 support, and tag rollback.

Suggested commit: `refactor(generation): disable legacy back half for new lessons`
