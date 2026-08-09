# 03 — Run 1 (Science) timeline

**Result: `PARTIAL` — the two blockers this task targeted are cleared and verified
in the browser, but the run did not reach the native viewer.** Stopped at the
user's instruction while the generation was executing.

## Identifiers

| Item | Value |
|---|---|
| Unit ID (used for preparation) | `a3c6c213-1da7-40ba-84c9-b0d9504daf2e` |
| Unit ID (fresh browser-only attempt, blocked at path:plan) | `c54736a5-c45b-4926-a749-37fb0b2b5b37` |
| Path version | `c7e39677-c925-47b7-a2c0-fcaa443c30cd`, v1, APPROVED |
| Selected lesson | Lesson 6 — "Why Light Is Needed" |
| Lesson ID | `482ee689-1706-43b5-af95-1c2f70b7e2d3` |
| **Generation ID** | **`474fcade-7e53-418a-9121-cc18286d8a3a`** |
| Lesson mode | `first_exposure` |
| Document contract version | **2 (native)** |

A generation ID existing at all is the headline result: across four attempts on
the starting commit, preparation never got far enough to create one.

## Stage timings (local, UTC+03:00)

| Marker | Stage | Time | Duration |
|---|---|---|---|
| T0 | Path requested (first browser attempt) | 14:06:17 | — |
| — | Unit created (`POST /units` → 201) | 14:07:49 | 1m 32s |
| — | `path:plan` → 500 ×3, → 422 ×1 | 14:07 – 14:48 | see `05-errors-and-retries.md` |
| T1 | Path available (persisted `c7e39677`) | 15:1x | — |
| T2 | **Path approved in browser** ("Looks good — lock it in") | ~15:33 | — |
| T3 | **Lesson preparation requested** | 15:35:59 | — |
| T4 | **`:prepare` → 200 OK**, generation created | 15:37:28 | **1m 29s** |
| T5 | Structural plan approved (`/v3/chunked/{id}/approve` → 200) | 15:47:33 / 15:55:25 | — |
| T6 | Status `running`, execution started | 15:56 | — |
| T7–T16 | Teaching approval, queued, worker, assembly, ready, viewer, PDF | **not reached** | — |

Path-planning timings are not reportable as product measurements: three of five
attempts died in the DB layer and one was rejected by product validation. The
timings that are clean are preparation (1m 29s) and structural approval.

## What was verified

### Blocker 1 — structural planner contract: **FIXED**

`POST .../path/lessons/482ee689-1706-43b5-af95-1c2f70b7e2d3:prepare → 200 OK` on
the first attempt.

On the starting commit the same call failed four times out of four:

```text
422  2 validation errors for SectionPlan
       id       Field required   (input_value={'slot_id': 'orient', ...})
       slot_id  Extra inputs are not permitted
409  Path preparation must produce exactly one concept card   (x3)
```

The persisted structural plan confirms the typed contract held:

```text
document_contract_version: 2
sections: 4
first section keys: ['blocks', 'card_id', 'components', 'id', 'role',
                     'title', 'transition_note', 'visual_required']
first blocks: 0        first components: 0
```

`id` is present, `slot_id` is absent, exactly one concept card, and `components`
is empty on the native path with blocks owned downstream — every invariant the new
models and validator enforce.

The rendered plan in Studio was coherent and on-objective:

```text
1. Why Does a Plant in the Dark Struggle?      ORIENT
2. Light: The Energy for Food-Making           EXPLAIN
3. Light: Trigger or Fuel?                     CONTRAST
4. Check Your Understanding                    CHECK
```

Section order and roles match the fixed skeleton slots, and the first section
carries no transition note while sections 2–4 do — the validator's rules, visible
in the product.

### Blocker 2 — form planner DeepSeek 400: **not reached**

The generation entered execution but the run was stopped before
`planning_forms` could be observed. The fix is covered by deterministic tests
(reasoning disabled for the node, `retries={"output": 0}` at the call site) but
**was not exercised against the live provider**. This is explicitly unproven.

### Native path, not legacy

`chunked_state_json` carries `native_whole_lesson`, `page_document_v2` and
`document_contract_version: 2`. No legacy `resume_stage2` call was made — the
"Resume generation" control was traced first and calls
`POST /v3/chunked/{id}/approve`, the same endpoint as normal structural approval.

## What was NOT verified

```text
teaching approval gates downstream       could not verify
approval returns queued asynchronously   could not verify
worker claims the job                    could not verify (this run)
planning_forms completes                 could not verify
writing_blocks / assembling              could not verify
DB-first assembly                        could not verify
reload_verified / hash match             could not verify
visual readiness                         could not verify
native LectioDocumentV2 renders          could not verify
PDF teacher/student divergence           not attempted
```

"Could not verify" means the code path was not reached, not that it is healthy.

One caveat on the teaching gate specifically: execution was reached through the
product's interruption-recovery control after the server dropped mid-approval, not
through the normal teaching-approval flow. So the gate was neither confirmed nor
shown to be bypassed — it was not observed.

## Why the run stopped

The backend degrades to returning 500 on essentially every request after some
minutes of uptime, and recovers only on restart (`05-errors-and-retries.md`, E1).
Each stage of this flow takes 1–6 minutes, so the run repeatedly outlived the
window in which the server was healthy. Combined with application logs being
unreadable (E2), progress required a restart-and-sprint cycle for each stage.

Stopped at the user's instruction.
