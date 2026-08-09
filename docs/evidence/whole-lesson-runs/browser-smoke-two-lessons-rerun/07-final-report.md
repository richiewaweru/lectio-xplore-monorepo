# 07 — Final report (rerun)

**Verdict: the two-lesson native browser path is NOT yet end-to-end operational.**

The blocker this task was created to fix is fixed and verified in the browser. The
run did not reach the native viewer, and Economics was not started. Per the
brief's own instruction, returning a generation ID is not success.

## Implementation

```text
Starting commit:  bb56f8997a1a4a0a28645c2f92820bd5dcf8afd7
Final commit:     0cc0ff3  fix(native-planning): unblock structural and form planner e2e
Files changed:    18 (11 source/script, 7 test)
```

| Fix | Status |
|---|---|
| Structural contract (typed `PathStructuralPlan`) | done, verified in browser |
| Structural repair attempt | done, unit-tested; did not need to fire live |
| Model/node policy (reasoning off for constrained nodes) | done, unit-tested |
| DeepSeek boundary (`retries={"output": 0}`) | done, verified empirically against pydantic-ai 1.107.1 |
| Alembic 0032 reconciliation | done, proven on a scratch DB and by live startup |
| Evidence CLI safe slugs | done, unit-tested |

Two departures from the brief, both put to the user and approved before
implementation, both documented in `01-implementation-summary.md`:

* nested models are `extra="ignore"`, not `extra="forbid"` — on the PromptedOutput
  path the schema is prompt text, so `forbid` cannot reduce drift, only convert
  drift the bridge already absorbs into new hard failures;
* `cards` has `max_length=1` but no `min_length=1` — a lower bound would destroy
  the planner's `objective_concern` escape hatch before the bridge could surface it.

## Tests

```text
Focused tests:      30 passed (structural models/validation/repair)
                    47 passed (retry boundary, capture CLI, node config)
                    14 passed (bridge)
Backend lint:       17 errors — identical set at the starting commit (proven by
                    linting a pristine git archive tree). No new lint errors.
Full backend suite: this branch 93 failed / 675 passed
                    bb56f89     152 failed / 551 passed
                    -> 59 fewer failures, 124 more passes
Frontend tests:     78 files, 323 tests, all pass
Frontend check:     1 error, 2 warnings — all pre-existing, in files this change
                    does not touch
Migration proof:    alembic upgrade head from empty on a scratch DB -> PASS,
                    stamp 20260806_0032; scratch DB dropped
```

The full suite is heavily order-dependent under this `.env`: files that fail in the
full run pass when run individually. That instability predates this change and is
worse at the starting commit.

## Browser result

| Run | Subject | Generation ID | Final status | Viewer | PDF | Total |
|---|---|---|---|---|---|---|
| 1 | Science G4 | `474fcade-7e53-418a-9121-cc18286d8a3a` | `running` (execution started) | not reached | not attempted | ~1h 50m wall, mostly environment recovery |
| 2 | Economics G8 | — | not started | — | — | — |

## Architecture proof

```text
structural approval gate:      confirmed   (/v3/chunked/{id}/approve -> 200, status advanced)
teaching approval gate:        could not verify
async queued response:         could not verify
worker claim:                  could not verify (this run; the worker's claim loop
                               was observed failing on DB errors — see E1)
form planner completion:       could not verify
DB-first assembly:             could not verify
reload/hash verification:      could not verify
visual readiness:              could not verify
native LectioDocumentV2:       confirmed in persisted state
                               (document_contract_version: 2, native_whole_lesson,
                               page_document_v2), NOT confirmed in the viewer
legacy resume_stage2:          not observed (the "Resume generation" control was
                               traced before use; it calls /v3/chunked/approve)
fixture use:                   not observed
```

## Remaining blockers

**1. Backend degrades to all-500s after minutes of uptime (environment/infra).**
Time-dependent, not request-duration dependent; affects short requests too; clears
on restart. `pool_pre_ping=True` and `pool_recycle=300` are already set, so
something defeats them in the long-lived process. Two of my hypotheses were tested
and rejected (server idle timeouts; NAT dropping idle TCP — a 300s idle hold
succeeded). This is what stopped the run. Full detail in `05-errors-and-retries.md` E1.

**2. Application logs are unreadable when redirected.** stdout is block-buffered
and four workarounds failed; buffered records are lost on kill. This was the
largest single drag on diagnosis and is why blocker 1 is characterised but not
root-caused.

**3. Form planner fix is unproven against the live provider.** Unit tests cover the
config and the retry boundary, but `planning_forms` was never reached, so the
DeepSeek 400 is not confirmed fixed in practice.

**4. `_run_structured` change is broader than intended.** Applied inside a helper
shared by six callers while only one has an outer repair loop. Tested and shown not
to be causing the observed failures, but it should be made opt-in per call.

**5. Path planner has no repair attempt.** Same weakness the structural planner
just had; produced a 422 on one attempt. Out of scope here, but the obvious next
candidate for the same fix.

## What I would do next, in order

1. Root-cause blocker 1 — instrument pool checkout/checkin and asyncpg connection
   lifetime. Nothing else can be trusted end-to-end until the server stays healthy.
2. Fix logging so application records reach a readable stream.
3. Rerun Science from lesson preparation and push through teaching approval to
   `ready`, which is the first real test of the form-planner fix.
4. Narrow `retries={"output": 0}` to the three loop-owning call sites.
5. Run Economics from the existing approved unit `887c1107`, starting at
   preparation.
6. Re-evaluate `V2_PATH_STRUCTURAL_PLANNER` reasoning — it was set to `False` as
   the brief required, but Blocker 1 was schema drift, not an empty response, so
   that change is unproven and may be costing plan quality for no benefit.

## Constraints honoured

```text
Source modified only as specified:        yes
Database rows edited:                     no
Manual status changes:                    no
Fabricated visual callbacks:              no
Approval gates bypassed:                  no
Fixtures used:                            no
Legacy resume_stage2 invoked:             no
Secrets committed:                        no
Prior evidence deleted:                   no
```

Two actions taken outside the browser, both disclosed: a diagnostic in-process
reproduction of the `path:plan` route (which persisted a real path version for unit
`a3c6c213`, because logs were unreadable and it was the only way to obtain a
traceback), and a scratch migration database created and dropped on the remote
server. Neither was used to make a run pass.
