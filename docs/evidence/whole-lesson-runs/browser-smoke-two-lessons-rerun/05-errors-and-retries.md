# 05 — Errors and issues encountered (rerun)

Ordered by severity. No bearer tokens or secret values appear here.

Two of my own working hypotheses were disproven during this run and are recorded
as such, because the wrong diagnosis was in play for a while and the corrections
matter.

---

## E1 — Long-lived backend process degrades until every request 500s (BLOCKER, environment)

```text
Severity:   Blocker — prevented the browser E2E from completing
Stage:      All stages; first hit at path:plan
Symptom:    After some minutes of uptime the server returns 500 to essentially
            every authenticated request. A restart fixes it immediately.
```

### Timeline

```text
14:07  path:plan            -> 500
14:21  path:plan            -> 500
14:31  path:plan            -> 500
       (backend restarted)
14:43  path:plan            -> 422  (product validation, see E3 — server was healthy)
15:19  path:plan            -> 500  (fresh unit)
15:2x  GET .../lessons/{id}/shape   -> 500   <-- a SHORT request, also failing
       GET .../lessons/{id}/status  -> 500
       (backend restarted)
15:3x  same two GETs               -> 200 OK
15:35  :prepare                    -> 200 OK
15:55  /v3/chunked/{id}/approve    -> 200 OK
```

The decisive observation is the pair at 15:2x/15:3x: two *short* GETs failed, then
succeeded after nothing changed but a process restart.

### Underlying error

```text
sqlalchemy.exc.DBAPIError: (sqlalchemy.dialects.postgresql.asyncpg.Error)
  <class 'asyncpg.exceptions.ConnectionDoesNotExistError'>:
  connection was closed in the middle of operation
ConnectionAbortedError: [WinError 1236] The network connection was aborted by the local system
```

The native worker's claim loop failed 10 consecutive times with the same error
(`whole_lesson/worker.py:73` → `:103` → `repository.py:976 claim_next_native_job`).

### Two hypotheses I tested and rejected

**Rejected — server-side idle timeouts.** Measured directly:

```text
idle_in_transaction_session_timeout = 0
statement_timeout                   = 0
idle_session_timeout                = 0
tcp_keepalives_idle                 = 7200
max_connections                     = 500   (25 in use)
```

Nothing on the server closes connections, and there is no connection-count
pressure.

**Rejected — an intermediary dropping long-idle TCP.** I first attributed this to
the route holding a connection across the multi-minute LLM phase
(`planning/routes.py:352` acquires, `:368-372` runs the planner and merge critics,
`:375` writes). A direct probe disproved it: holding a connection idle for 60s,
180s and 300s all succeeded, and 10/10 short queries succeeded.

The same full route sequence — fetch unit, run planner, run 5 merge critics,
persist, commit — **succeeded when run in a short-lived script** while failing
through the server. The difference is process lifetime, not request duration.

### What the evidence actually supports

The engine already sets `pool_pre_ping=True` and `pool_recycle=300`
(`core/database/session.py:12-17`), so stale connections should be caught at
checkout. Something in the long-lived process defeats that: connections that pass
checkout are dead by the time they are used, and once the process reaches that
state it does not recover on its own.

I did not isolate the precise mechanism. What is established:

* it is time/uptime dependent, not request-duration dependent;
* it affects short requests too;
* a restart clears it completely;
* it is independent of this change — the same code path succeeds in a fresh
  process, and `path:plan` succeeded twice on the starting commit earlier in the day.

**Suggested next step:** log pool checkout/checkin events and asyncpg connection
lifetime, and confirm whether `pool_pre_ping` is actually firing against this
provider. Also worth testing whether the remote provider terminates connections
in a way asyncpg does not surface until first use.

### Note on the database

`DATABASE_URL` points at a **hosted remote Postgres** (database name `railway`),
not a local instance. An earlier note of mine described the migration-proof scratch
database as being on a local server; that was wrong. `lectio_migration_proof` was
created on the same remote server as `DATABASE_URL` and was dropped cleanly at the
end of the proof. The application database was never used for migration
experiments.

---

## E2 — Backend application logs are unreadable when redirected (BLOCKER for diagnosis)

`configure_logging` writes JSON records to stdout, which Python block-buffers when
stdout is a file or pipe. Four approaches were tried:

```text
PowerShell Tee-Object                                  -> flushed in large chunks, minutes late
Start-Process -RedirectStandardOutput + python -u      -> 0 bytes written
PYTHONUNBUFFERED=1                                     -> no effect
JSON_LOGS=false                                        -> no effect (stream unchanged)
```

Only uvicorn's own startup lines (stderr) ever appeared. On a hard kill the
buffered records are lost outright — I killed a process specifically to flush the
buffer and got nothing.

**This was the single biggest drag on the run.** The first three `path:plan` 500s
produced no readable server-side error at all, which is what sent me down the
rejected hypotheses in E1. Every diagnosis after that had to be recovered by
querying the database directly, reproducing calls in-process, and reading the
browser network panel.

Not fixed here — it is a logging-configuration change outside the requested scope
— but an operator debugging a production incident would hit exactly this wall.

---

## E3 — Path planner produces plans that fail its own validation (product, no repair)

```text
Stage:  POST .../path:plan
HTTP:   422
```

```text
That change leaves open prerequisite risks while still claiming the path
reaches its destination.
```

Raised by `validate_path_plan`, called from `run_path_planner`
(`planning/agents.py:117`) after the model returns. There is no repair attempt:

```python
plan = await _run_structured(...)
plan = normalize_declared_external_prerequisites(plan)
validate_path_plan(plan)      # raises PathValidationError -> 422
return plan
```

Pre-existing and unaffected by this change. This is our own semantic validation,
not pydantic-ai output validation, so `retries={"output": 0}` does not touch it.

It is the same structural weakness the brief asked to fix for the *structural*
planner — strong schema plus one targeted repair — and the path planner still has
it. Fixing it was outside the requested scope, but it is a strong candidate for
the same treatment.

Plan size also varied a lot across attempts for identical input: 8 lessons, then
6, then 6. Lesson count is model-determined and drives how many merge-critic calls
follow, so `path:plan` latency is inherently variable.

---

## E4 — `_run_structured` is shared by six nodes but only one owns a repair loop (RISK, unresolved)

`retries={"output": 0}` was applied inside `_run_structured`
(`planning/agents.py`), the shared helper for **six** callers: `run_path_planner`,
`run_merge_critic`, `run_component_selector`, `run_path_structural_planner`,
`run_constructor`, `run_plan_chat_edit`.

Only `run_path_structural_planner` gained an outer repair loop in this change. The
other five lost pydantic-ai's single free self-correction on a malformed
structured response.

I suspected this was causing the `path:plan` 500s and **tested it rather than
assuming**: calling `run_path_planner` directly with the same inputs returned a
valid 8-lesson plan, and the actual failure was E1. So no observed failure is
attributable to it.

It remains a real sharp edge. **Recommended follow-up:** make the parameter opt-in
per call — pass it only from `run_path_structural_planner` (and the form/teaching
agents, which have their own loops) — rather than applying it inside the shared
helper. I did not make that change because no evidence demanded it and I did not
want an untested edit going in at the end of a run.

---

## E5 — Studio SSE stream aborts continuously

```text
GET /api/v1/v3/chunked/{id}/events   [FAILED: net::ERR_ABORTED]   x many
```

The Studio page retries the event stream in a tight loop. Progress had to be read
from the database instead. This coincided with E1 degradation, so it may be a
symptom rather than an independent defect — I could not separate them.

---

## E6 — Browser pane instability

The in-app browser became unresponsive once (`get_page_text` and `screenshot` both
timed out for 30s), and a second tab would not accept clicks at all — coordinates
registered but no handler fired, so all work had to run in the original tab.
Ref-based clicks also map to wrong coordinates; every click in this run was done
by screenshot pixel coordinates.

---

## Process notes — mistakes I made

Recorded because they affected the evidence, not to pad the list.

1. **I diagnosed E1 twice before getting it right.** Server-side idle timeout, then
   NAT dropping idle TCP. Both were plausible and both were wrong. The correction
   came from probes I should have run before writing the first diagnosis down.

2. **I ran the full route in-process to get a traceback, which persisted a real
   path version** for unit `a3c6c213` (version `c7e39677-c925-47b7-a2c0-fcaa443c30cd`).
   That was a diagnostic action, but it means that unit's path was not created
   through the browser. I set the unit aside and started a fresh browser-only unit
   (`c54736a5`) — which then hit E1 — and ultimately returned to `a3c6c213` to
   exercise lesson preparation. **The lesson-preparation evidence is browser-driven;
   that unit's path planning was not.** This is stated plainly rather than glossed.

3. **I clicked "Resume generation" before fully tracing it.** I checked it calls
   `POST /v3/chunked/{id}/approve` and not legacy `resume_stage2`, which was the
   constraint I cared about — but I had not traced that the frontend then runs
   `continueChunkedStage2`. The generation is confirmed native
   (`document_contract_version: 2`, `native_whole_lesson` and `page_document_v2`
   present in `chunked_state_json`), so no legacy conversion occurred. But I
   cannot claim the native teaching-approval gate was observed, because I reached
   execution through the product's interruption-recovery path rather than through
   the normal teaching-approval flow.

---

## Retry accounting

```text
path:plan   x5  (3 environment 500s, 1 product 422, 1 completed)
:prepare    x1  -> 200 OK, first attempt, no retry needed
approve     x2  ("Review concepts", then "Resume generation" after interruption)
```

No database row was edited, no status was changed by hand, no fabricated callback
was sent, and no replacement generation was created to dodge a failure. The only
database writes outside the browser were the diagnostic route reproduction noted
above and the scratch migration database, which was dropped.
