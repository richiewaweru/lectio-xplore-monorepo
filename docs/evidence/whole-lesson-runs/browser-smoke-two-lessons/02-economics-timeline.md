# 02 — Run B (Economics) timeline

**Result: `FAIL_GENERATION`** — blocked at the same structural-plan gate as Run A.
No `generation_id` was ever issued.

## Identifiers

| Item | Value |
|---|---|
| Unit ID | `887c1107-21b3-4be8-9ef1-11e100556067` |
| Unit title | Explain how scarcity forces choices and creates opportunity cost |
| Subject / grade | Economics · Grade 8 |
| Path version | v1, `path_planner`, APPROVED |
| Selected lesson | Lesson 6 — "Connecting Scarcity to Opportunity Cost" |
| Lesson ID | `887f71be-5a17-470f-8e36-f2a4f3ff9fd0` |
| Concept ID | `c749264b-2b46-49ff-91ae-cc3d3fbb…` (truncated in UI) |
| Lesson mode | `first_exposure` |
| Generation ID | **none issued — preparation never succeeded** |

Lesson selection rationale: the destination objective is "Explain how scarcity
forces choices and creates opportunity cost." Lesson 6 is the only lesson that
joins both halves of that objective; lessons 1–5 are prerequisites. It was chosen
despite being the last and most dependent lesson, rather than substituting an
earlier lesson that would have completed sooner.

## Stage timings (local time, UTC+03:00)

| Marker | Stage | Time | Duration |
|---|---|---|---|
| T0 | Path requested ("Plan it" submitted) | 08:45:17 | — |
| — | `POST /units/constructor/readback` → 200 | 08:45:33 | 16s |
| — | Readback confirmed; `POST /units` → 201 | 08:47:07 | 1m 34s |
| T1 | `POST /units/{id}/path:plan` → **201**, 6 lessons visible | 08:50:07 | **3m 00s** |
| — | Assumption resolved in UI ("Keep apart") | ~08:51:30 | — |
| T2 | `POST /units/{id}/path:approve` → **200** ("Locked in") | 08:51:45 | ~15s |
| T3 | Lesson preparation requested (attempt 1) | 08:54:09 | — |
| T4 | **Structural plan FAILED** — `:prepare` → **409** | 08:55:38 | **1m 29s to failure** |
| T3b | Lesson preparation requested (attempt 2, one permitted product retry) | ~08:56:35 | — |
| T4b | **Structural plan FAILED again** — `:prepare` → **409** | 08:58:03 | **1m 28s to failure** |
| T5–T16 | Structural approval onward | **never reached** | — |

Total elapsed from T0 to terminal failure: **12m 46s**.

### Derived timings

```text
path planning          3m 00s
path approval          <1s server-side
lesson preparation     1m 29s to 409 (attempt 1)
                       1m 28s to 409 (attempt 2)
teaching-plan wait     not reached
approval response      not reached
form planning          not reached
writing                not reached
assembly               not reached
visual wait            not reached
ready-to-view          not reached
PDF time               not reached
total time             12m 46s (T0 -> terminal failure)
```

## What was verified before the failure

* The readback correctly extracted the destination objective and the starting
  knowledge.
* The path planner produced a 6-lesson progression with correct dependency edges:
  1. Defining Scarcity
  2. Scarcity Forces Choices *(needs 1)*
  3. Trade-offs *(needs 2)*
  4. Defining Opportunity Cost *(needs 3)*
  5. Identifying Opportunity Cost *(needs 4)*
  6. Connecting Scarcity to Opportunity Cost *(needs 2, 3, 5)*
* **An assumption was raised and resolved through the UI**, which Run A did not
  exercise. The planner proposed merging lessons 3 and 4:

  > "Lessons 3 and 4 might work as one lesson — Opportunity cost is a direct
  > refinement of trade-off (the next best alternative), and a merged quiz can
  > still distinguish a learner who grasps the general trade-off concept from one
  > who does not understand the specific definition of opportunity cost."

  Resolved as **"Keep apart"**, on the grounds that the destination objective names
  scarcity, choice, and opportunity cost as distinct ideas. The unit accepted the
  resolution and the merge prompt disappeared.
* Path approval flipped the unit to LOCKED IN.

The assumption-resolution UI worked correctly.

## Failures

Both attempts returned **409** with the identical message:

```text
Path preparation must produce exactly one concept card
```

```text
attempt 1: POST .../path/lessons/887f71be-5a17-470f-8e36-f2a4f3ff9fd0:prepare -> 409
           2026-08-06T05:55:38Z
attempt 2: POST .../path/lessons/887f71be-5a17-470f-8e36-f2a4f3ff9fd0:prepare -> 409
           2026-08-06T05:58:03Z
```

## Diagnosis

Same root cause as Run A (see `03-error-log.md`, E1): `PathStructuralPlan.cards` is
declared `list[dict]` at `planning/models.py:385`, so the structured-output
contract does not constrain the number of concept cards. The model returned a
number other than one, and `planning/bridge.py` rejects it.

Run B is the stronger evidence that this is systemic rather than incidental:

* a different subject (Economics vs Science),
* a different grade (8 vs 4),
* a different lesson shape instance,
* four preparation attempts across the two runs,
* **zero** successes.

## Database confirmation

Queried directly after both runs:

```text
generations created during this run window: 0
alembic_version still: ['20260806_0032']
```

No generation row was created for either unit. Nothing was queued, so the native
worker, lease handling, DB-first assembly, reload/hash verification, visual gating,
and the native viewer were never exercised by this run. The `alembic_version` value
is unchanged, confirming no database edits were made.
