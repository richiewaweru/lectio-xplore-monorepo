# Phase 02 Verification Protocol

## Principle

Browser automation is not required. Proof is operational:

```text
API + DB + logs/events + failure injection + restart/reclaim
+ fresh document reload + direct PDF calls + PDF assertions
```

## Test layers

### Unit

State transitions, execution keys, retry classification, outcome serialization, expected-key enumeration, teacher/student projection.

### Repository integration

Atomic claim, two-worker contention, heartbeat, stale reclaim, transition atomicity, block persistence, form-plan reuse, fresh-session reload.

### Local API smoke

```text
create unit → plan path → approve path → prepare lesson
→ wait teaching plan → approve teaching → poll status
→ fetch document → teacher PDF → student PDF
```

### Resilience run

Inject one retryable middle-block failure. Prior and later siblings must survive; restart backend; reclaim; skip ready; retry failed; assemble from DB.

### Four-run proof

Four subjects from one commit. Quality is recorded but is not a Phase 02 pass condition unless structurally invalid.

## Approval

Pass: HTTP 202, local response target under two seconds, status queued. Record actual timing.

## Worker claim

Two concurrent claim attempts: exactly one true, one false, one stored worker ID.

## Heartbeat

During a delayed substitute, heartbeat advances more than once; fresh jobs are not reclaimed; after termination and lease expiry another worker claims.

## Failure injection

Use dependency injection or a test-only environment variable such as:

```text
FAIL_NATIVE_BLOCK_ONCE=explain:explain-b2:everyone
```

It must be disabled by default, test-mode only, fail once then succeed, and record a structured error.

## Resume assertions

Before/after restart compare ready keys, content hashes, and attempts. Ready hashes and attempts remain unchanged; failed key attempt increments; no duplicate ready event is emitted for skipped work.

## DB-first assembly

Acceptable proof: restart after block persistence but before assembly, invoke assembly in a fresh process/session, or integration-test with no in-memory results. Final document must contain every expected block in form-plan order.

## Fresh reload

Close current session; open new session; reload generation; parse and validate native document; compare persisted/reloaded stable fields and hashes.

## Pending visuals

Before completion: stage `awaiting_visuals`, PDF conflict. After callback: same block ID/position, asset updated, revision incremented, stage ready, PDF succeeds.

## PDF assertions

Record pages, answer phrase, teacher contains answer, student excludes answer, files differ, and parser errors. Both PDFs must open and have nonzero pages.

## Legacy exclusion

Every new run is dcv2 and has no `resume_stage2`, legacy section brief, booklet assembly, or legacy pack coercion.

## Completion threshold

```text
forced failure/restart run passes
AND teacher/student PDF pair passes
AND four official runs complete from one commit
```
