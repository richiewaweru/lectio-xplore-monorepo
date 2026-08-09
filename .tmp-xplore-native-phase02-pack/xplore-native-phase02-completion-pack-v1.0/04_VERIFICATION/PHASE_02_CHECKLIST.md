# Phase 02 Verification Checklist

## State
- [ ] One canonical transition method.
- [ ] `GenerationModel.status` authoritative.
- [ ] Compatibility stage mirrors it.
- [ ] Illegal transitions rejected.
- [ ] Structured, nonempty errors persisted.

## Approval/queue
- [ ] Approval returns 202 promptly.
- [ ] No inline form/writer execution.
- [ ] Duplicate approval idempotent.
- [ ] Queued state visible.

## Worker
- [ ] Atomic claim.
- [ ] Worker ID persisted.
- [ ] Heartbeat during long calls.
- [ ] Stale reclaim works.
- [ ] Two workers cannot co-own.
- [ ] Restart does not lose work.

## Form
- [ ] Persisted form plan reused.
- [ ] No form rerun after restart.
- [ ] Transport backoff.
- [ ] One validation repair.

## Blocks
- [ ] Composite key includes section/block/variant.
- [ ] Ready and visual-pending skip.
- [ ] Retryable failed retries.
- [ ] Terminal failed does not auto-retry.
- [ ] Max concurrency 3.
- [ ] Failure does not cancel siblings.
- [ ] Attempts/timestamps/errors persisted.

## Assembly
- [ ] Form plan reloaded from DB.
- [ ] Outcomes reloaded from DB.
- [ ] Local writer list not authoritative.
- [ ] Missing/failed/duplicate/unknown/mismatch rejected.
- [ ] Order follows form plan.
- [ ] Native document validates.
- [ ] Fresh-session reload validates.

## Figures
- [ ] Stable request ID survives retry.
- [ ] Pending figure preserves identity.
- [ ] Awaiting-visuals state works.
- [ ] PDF blocked while pending.
- [ ] Callback idempotent.
- [ ] Revision increments.
- [ ] Ready when requirements complete.

## PDFs
- [ ] Teacher PDF opens and has pages.
- [ ] Student PDF opens and has pages.
- [ ] Teacher contains answer phrase.
- [ ] Student excludes it.
- [ ] Files differ.
- [ ] Native document used directly.
- [ ] No legacy conversion.

## Failure/restart
- [ ] Middle block fails once.
- [ ] Later siblings complete.
- [ ] Backend stops/restarts.
- [ ] Job reclaimed.
- [ ] Ready hashes unchanged.
- [ ] Ready attempts unchanged.
- [ ] Failed attempt increments.
- [ ] DB-first assembly succeeds.
- [ ] Native reload succeeds.

## Four runs
- [ ] Science.
- [ ] Mathematics.
- [ ] Economics.
- [ ] English.
- [ ] One commit for all.
- [ ] Prompts/responses recorded.
- [ ] Latency/tokens/cost recorded where available.
- [ ] Teacher/student PDFs recorded.
- [ ] No fixture.
- [ ] No `resume_stage2`.
- [ ] No legacy conversion.

## Legacy shutdown
- [ ] Native proof completed first.
- [ ] New-generation legacy branch disabled.
- [ ] Historical v1 read-only remains.
- [ ] Rollback tag created.
