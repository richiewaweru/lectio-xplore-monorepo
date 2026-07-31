# Current System and Required Defect Fixes

## Existing Xplore strengths

Preserve:

- one structural-planner call;
- ConceptCard and Misconception models;
- durable `awaiting_review`;
- item generation from card-only context;
- one shared item set per pack;
- up to three concurrent variants;
- sibling failure isolation;
- teacher-edit preservation;
- QC verdict recomputation;
- diagnostic answer-key printing;
- Builder editing;
- Lectio rendering.

## Defect 1 — Dead role validation

Current behavior:

- validator looks for role definitions absent from active resource spec;
- empty allowed-role set causes validation to skip;
- planner invents free-text roles.

### Required correction

Make `skeletons.yaml` the source of truth for slot roles.

- Structural skeleton expansion emits roles deterministically.
- Planner no longer invents section roles.
- Validation rejects unknown slot/role values.
- Existing legacy plans are handled through compatibility parsing, not silent acceptance.

## Defect 2 — Planner lacks component cognitive jobs

### Required correction

Component-selection context must include:

- slug;
- cognitive job;
- allowed slot(s);
- component field constraints;
- renderer availability.

The LLM chooses components only within a deterministic slot.

## Defect 3 — StructuralPlan silently ignores unknown fields

### Required correction

Return `StructuralPlan` to `extra="forbid"`.

For old persisted plans:

- write an explicit legacy adapter;
- strip only named legacy fields;
- log adaptation;
- do not silently ignore arbitrary keys.

## Defect 4 — Six-section hard bound

Retain initially because current rendering and validation assume it.

Skeleton rules must guarantee maximum six slots after toggles.

A future decision to increase it requires separate validation.

## Defect 5 — Multiple cards per lesson

Current live behavior allows multiple cards.

### Required correction

New path-prepared lessons have exactly one canonical concept/card.

Legacy plans may retain multiple cards.

New invariant applies only to V2 path-prepared lessons until migration is deliberate.

## Defect 6 — Misconception quota

Change from forced 2–4 to validated 0–3.

The existing belief test remains:

> Could a learner holding this belief confidently choose a corresponding wrong answer?

## Regression requirement

Every defect above requires a failing regression test before the fix and a passing test after.
