# 03 — Error log

Issues are ordered by severity. Bearer tokens are not reproduced anywhere in this
evidence set.

---

## E1 — Native structural planner emits an unenforced shape; preparation rejects it (BLOCKER)

```text
Severity:           Blocker — stops the native whole-lesson path before it starts
Run:                A (Science). Reproduced twice, with two different violations.
Stage:              Lesson preparation / structural plan (T4)
Lesson:             ac52e5a0-4053-46aa-8938-cb9634593334
Generation ID:      none — preparation never succeeded, so none was issued
Timestamps:         2026-08-06T05:37:43Z (attempt 1), 2026-08-06T05:41:57Z (attempt 2)
UI state:           "Making the lesson…" then an error banner; lesson stayed "unprepared"
HTTP:               POST /api/v1/units/{unit}/path/lessons/{lesson}:prepare
                      attempt 1 -> 422
                      attempt 2 -> 409
```

Sanitized responses:

```text
attempt 1 (422)
  2 validation errors for SectionPlan
  id        Field required [type=missing,
              input_value={'slot_id': 'orient', 'ro...ents': [], 'blocks': []},
              input_type=dict]
  slot_id   Extra inputs are not permitted [type=extra_forbidden,
              input_value='orient', input_type=str]

attempt 2 (409)
  Path preparation must produce exactly one concept card
```

```text
Automatic retry:    None at this stage. The structural planner has no repair or
                    re-ask loop, unlike the form planner which retries twice.
Recovery result:    Not recovered. The one permitted product retry produced a
                    second, different violation of the same contract.
Final status:       unprepared (never queued, never generated)
Likely subsystem:   planning bridge / structural planner schema contract
Diagnosis conf.:    High
```

**Cause.** `PathStructuralPlan` is the structured-output type handed to the
provider (`planning/agents.py:204`), and it declares its two most important
fields as untyped containers — `planning/models.py:383`:

```python
class PathStructuralPlan(StrictModel):
    anchor: PathAnchor
    cards: list[dict]        # unconstrained -> card count not enforced
    sections: list[dict]     # unconstrained -> section keys not enforced
```

The provider is therefore never told that sections need `id` or that exactly one
card is required. The prompt says so in prose only
(`resources/path-structural-planner-page-v1.txt:55`), which the model is free to
ignore — and did, differently, on each attempt.

The result is then validated *strictly* at `planning/bridge.py:260` against
`v3_blueprint.planning.models.SectionPlan`, which is `extra="forbid"` and requires
`id`. Any drift is fatal.

`blocks` is a red herring: `SectionPlan` legitimately declares `blocks`
(`v3_blueprint/planning/models.py:136`) and `bridge.py:253-258` fills it on the
native path. The mismatch is `slot_id` vs `id`, plus card cardinality.

**Smallest fix:** give `PathStructuralPlan.sections` and `.cards` real typed
models (or `conlist(..., min_length=1, max_length=1)` for cards) so the contract is
enforced at generation time rather than discovered at validation time. A repair
retry on this stage would reduce flakiness but would not address the root cause.

---

## E2 — Native worker job fails at `planning_forms` on a provider 400 (BLOCKER, independent)

```text
Severity:           Blocker — the worker stage the run never reached is also broken
Run:                Pre-existing queued generation, NOT created by this run
Generation ID:      890c7cb8-5ccb-4b31-adbb-fb336b766e14
Stage:              planning_forms (native worker, worker_id=native-241781c19489)
Timestamp:          2026-08-06T05:27:03Z
UI state:           not observed in browser — surfaced in backend log at startup
HTTP:               provider call POST https://api.deepseek.com/chat/completions -> 400
```

Sanitized backend error:

```text
ERROR planning.whole_lesson.worker:
native worker job failed generation_id=890c7cb8-5ccb-4b31-adbb-fb336b766e14
worker_id=native-241781c19489
Traceback (most recent call last):
  planning/whole_lesson/worker.py:85   in _loop        -> await self._run_job(claimed)
  planning/whole_lesson/worker.py:142  in _run_job     -> await execute_after_teaching_approval(
  planning/whole_lesson/executor.py:660 in execute_after_teaching_approval
                                                       -> form_result = await run_form_planner(
  planning/whole_lesson/form_agent.py:174 in run_form_planner
      raise RuntimeError(f"form planner failed after 2 attempts: {last_error}")
RuntimeError: form planner failed after 2 attempts:
  status_code: 400, model_name: deepseek-v4-flash,
  body: {'message': 'Invalid assistant message: content or tool_calls must be set',
         'type': 'invalid_request_error', 'param': None, 'code': 'invalid_request_error'}
```

```text
Automatic retry:    Yes — 2 attempts inside run_form_planner. Both failed identically.
Recovered:          No.
Final status:       job failed
Likely subsystem:   form planner <-> deepseek provider adapter (pydantic-ai)
Diagnosis conf.:    Medium-high
```

**Cause.** The form planner is configured against `deepseek-v4-flash` with
`reasoning_effort: low` and `extra_json.thinking.enabled` (observed in the request
body in the backend log). The model returns an assistant message whose `content` is
empty (thinking-only), and when that message is replayed in the next request
DeepSeek rejects it with 400 *"Invalid assistant message: content or tool_calls
must be set"*. Retrying does not help because the shape is reproduced each time.

This matters because it is **a second, independent blocker on the same path**. Even
if E1 were fixed and a generation reached `queued`, the worker would fail at
`planning_forms`. It was observed on a leftover job rather than one of this run's,
so its exact behaviour under this run's inputs is inferred, not proven.

**Evidence:** `logs/backend-native-execution.log`.

---

## E3 — Backend cannot start: database stamped at a migration that does not exist (BLOCKER, environment)

```text
Severity:           Blocker for startup; worked around without editing DB or source
Run:                Preflight
Stage:              Backend startup (alembic upgrade on lifespan, app.py:224)
Timestamp:          2026-08-06 ~08:15-08:24 +03:00
UI state:           n/a
HTTP:               n/a — process exited with code 3 before binding
```

```text
alembic.util.exc.CommandError: Can't locate revision identified by '20260806_0032'
```

The `alembic_version` table holds `20260806_0032`. That revision exists in no file
and on no branch; the newest migration on disk is
`20260803_0031_add_generation_steps.py`. It was applied by a migration file that was
later deleted or never committed. Because `run_migrations_on_startup` defaults to
`True` (`core/config.py:231`), every backend start fails.

The failure is silent from the operator's point of view: uvicorn logs
"Waiting for application startup", prints the two alembic INFO lines, and exits 3
with no traceback, because the CommandError is raised inside
`asyncio.to_thread(upgrade_database)` during lifespan startup.

```text
Automatic retry:    None.
Recovered:          Yes — started with RUN_MIGRATIONS_ON_STARTUP=false after
                    verifying the live schema satisfies every ORM table and column
                    at HEAD (29 model tables, 31 db tables, zero missing columns).
                    No source edit, no DB write, alembic_version NOT re-stamped.
Likely subsystem:   migrations / repository hygiene
Diagnosis conf.:    High
```

**Smallest fix:** either commit the missing `20260806_0032` migration, or stamp the
database back to `20260803_0031` if that revision's changes are already present.
A startup guard that reports "database is ahead of this checkout" would turn a
silent exit-3 into a diagnosable message.

---

## E4 — Stale dev servers from the previous day silently served old code (WARNING, environment)

```text
Severity:           Warning — would have invalidated the whole run if unnoticed
Stage:              Preflight
```

Port 8000 was held by a python process started 2026-08-05 20:31 and port 5173 by a
node process started 2026-08-05 11:39. HEAD was committed 2026-08-06 07:43, so the
backend answering `/health` was running pre-HEAD code. `/health` returned a healthy
200 the whole time and gave no indication of this; only `started_at` in the payload
revealed it.

Both were stopped and replaced with fresh servers at HEAD before any lesson was run.
Because `vite` silently falls back to the next free port, the first frontend start
also landed on 5174 rather than 5173, which would have broken the OAuth origin; it
was restarted with `--strictPort` on 5173.

---

## Not observed

The following failure categories from the brief could not be exercised, because no
run ever reached the worker with a generation of its own:

* queued job never claimed — **not observed** (the worker did claim the leftover job
  promptly, which is positive evidence the claim loop works)
* lease loss / repeated reclaim / backward state transitions — **not observed**
* terminal generation with missing outcomes — **not observed**
* assembly missing/unknown-key error — **not observed**
* persisted/reloaded hash mismatch, `reload_verified=false` — **not observed**
* ready with unresolved visual — **not observed**
* legacy `resume_stage2` — **not observed**
* fixture or placeholder generation — **not observed**
* teacher/student export parity — **not observed** (no document to export)

"Not observed" here means the code path was never reached, not that it was
confirmed healthy.
