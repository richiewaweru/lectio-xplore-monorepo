# 01 — Run A (Science) timeline

**Result: `FAIL_GENERATION`** — blocked at the structural-plan stage (T4). The
generation never reached teaching approval, never entered the queue, and no
`generation_id` was ever issued.

## Identifiers

| Item | Value |
|---|---|
| Unit ID | `4d822228-ae51-4020-bf5e-72525640b6ab` |
| Unit title | Explain why plants need light to make food |
| Subject / grade | Science · Grade 4 |
| Path version | v1, `path_planner`, APPROVED |
| Selected lesson | Lesson 4 — "Why light is needed" |
| Lesson ID | `ac52e5a0-4053-46aa-8938-cb9634593334` |
| Concept ID | `5126e811-c618-4065-b10d-8abf5a2e02ec` |
| Lesson mode | `first_exposure` |
| Generation ID | **none issued — preparation never succeeded** |

Lesson selection rationale: the destination objective is "Explain why plants need
light to make food." Of the four planned lessons, Lesson 4 "Why light is needed" is
the destination lesson and the one most directly on the objective. Lesson 3 ("What
plants need to make food") is a prerequisite and was deliberately not substituted.

## Stage timings (local time, UTC+03:00)

| Marker | Stage | Time | Duration |
|---|---|---|---|
| T0 | Path requested ("Plan it" submitted) | 08:29:19 | — |
| — | `POST /units/constructor/readback` → 200 | 08:29:34 | 15s |
| — | Readback confirmed ("That's right"); `POST /units` → 201 | 08:30:05 | 31s |
| T1 | `POST /units/{id}/path:plan` → **201**, 4 lessons visible | 08:32:54 | **2m 49s** |
| T2 | `POST /units/{id}/path:approve` → **200** ("Locked in") | 08:35:11 | 17s (incl. UI review) |
| T3 | Lesson preparation requested (`:prepare`, attempt 1) | ~08:36:00 | — |
| T4 | **Structural plan FAILED** — `:prepare` → **422** | 08:37:43 | **1m 43s to failure** |
| T3b | Lesson preparation requested (attempt 2, one permitted product retry) | 08:40:30 | — |
| T4b | **Structural plan FAILED again** — `:prepare` → **409** | 08:41:57 | **1m 27s to failure** |
| T5–T16 | Structural approval, teaching plan, approval, queue, worker, assembly, viewer, PDF | **never reached** | — |

Total elapsed from T0 to terminal failure: **12m 38s**.

### Derived timings

```text
path planning          2m 49s   (POST /units 201 -> path:plan 201)
path approval          <1s server-side (200 returned promptly)
lesson preparation     1m 43s to 422 (attempt 1)
                       1m 27s to 409 (attempt 2)
teaching-plan wait     not reached
approval response      not reached
form planning          not reached
writing                not reached
assembly               not reached
visual wait            not reached
ready-to-view          not reached
PDF time               not reached
total time             12m 38s (T0 -> terminal failure)
```

No state was "not separately observable"; the run simply never produced the later
states.

## What was verified before the failure

* The readback correctly extracted the destination objective and both items of
  starting knowledge, unprompted.
* The path planner produced a coherent 4-lesson progression with dependencies:
  1. Plants make their own food
  2. Leaves are where food is made *(needs lesson 1)*
  3. What plants need to make food *(needs lessons 1, 2)*
  4. Why light is needed *(needs lessons 2, 3)*
* The lesson shape was `conceptual.first_exposure` with the canonical slot skeleton
  `orient → explain → contrast → confront → check`, plus high/medium/low support
  variants. This is the correct native shape.
* Path approval flipped the unit to LOCKED IN and the path version to APPROVED.

Everything up to and including path approval behaved correctly.

## Failure 1 — `:prepare` → HTTP 422

`POST /api/v1/units/4d822228-ae51-4020-bf5e-72525640b6ab/path/lessons/ac52e5a0-4053-46aa-8938-cb9634593334:prepare`
returned 422 at 05:37:43Z. Error surfaced directly in the UI:

```text
2 validation errors for SectionPlan
id
  Field required [type=missing,
   input_value={'slot_id': 'orient', 'ro...ents': [], 'blocks': []},
   input_type=dict]
slot_id
  Extra inputs are not permitted [type=extra_forbidden,
   input_value='orient', input_type=str]
```

## Failure 2 — `:prepare` → HTTP 409 (retry)

The one permitted product retry ("Make the lesson" again) produced a *different*
failure from the same stage at 05:41:57Z:

```text
Path preparation must produce exactly one concept card
```

Two different malformed structural-planner outputs in two consecutive attempts.

## Diagnosis

The structural planner's output shape is not enforced by the structured-output
contract, so the model is free to emit the wrong keys and the wrong cardinality,
and a strict validator downstream then rejects it.

`apps/textbook-agent/backend/src/planning/models.py:383`

```python
class PathStructuralPlan(StrictModel):
    anchor: PathAnchor
    cards: list[dict]        # <-- unconstrained
    sections: list[dict]     # <-- unconstrained
    deviation_request: PathDeviationRequest | None
    objective_concern: str | None
```

`cards` and `sections` are untyped `list[dict]`. `PathStructuralPlan` is what is
handed to the provider as the structured-output schema in
`planning/agents.py:204 run_path_structural_planner`, so the provider is told
nothing about the required section keys or the required card count.

The prompt does state the contract in prose —
`backend/resources/path-structural-planner-page-v1.txt:55`:

```text
- sections with id, title, role, card_id, visual_required, transition_note
```

— but prose is not enforcement. `deepseek-v4-flash` emitted `slot_id` instead of
`id` on attempt 1 (plausibly contaminated by the teaching/form planner schemas,
which legitimately use `slot_id`), and the wrong number of concept cards on
attempt 2.

The output is then validated strictly at
`apps/textbook-agent/backend/src/planning/bridge.py:260`:

```python
sections = [SectionPlan.model_validate(section) for section in section_payloads]
```

against `v3_blueprint.planning.models.SectionPlan`, which sets
`model_config = ConfigDict(extra="forbid")` and requires `id`. A `slot_id` key is
therefore fatal, with no repair or re-ask step for this stage.

Note that `blocks` is *not* the problem — `SectionPlan` legitimately declares
`blocks` (`v3_blueprint/planning/models.py:136`) for
`document_contract_version=2`, and `bridge.py:253-258` populates it on the native
path. The failure is specifically `slot_id` vs `id`, and card cardinality.

**Likely subsystem:** planning bridge / structural planner schema contract.
**Diagnosis confidence:** high — the failing key is named in the error, both
models are in the repo, and the retry produced a second violation of the same
unconstrained schema.

This is a code/contract defect at HEAD, not an environment or credentials problem.
The provider answered every call with HTTP 200; the content simply did not match a
contract that was never imposed on it.
