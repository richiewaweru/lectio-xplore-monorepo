# Patch to `xplore-learning-platform-v2-handoff`

This patch adds only what is missing from the V2 handoff. It changes no
decision. D1–D13 stand as written; the implementation phases stand as written.

Apply it by copying the files into the handoff folder as shown below, then
follow the handoff as normal.

```
xplore-learning-platform-v2-handoff/
├── 20_PROMPT_PACK.md                                    ← NEW
├── schemas/
│   └── path-plan.schema.json                            ← NEW
└── fixtures/
    ├── grade4-photosynthesis-path.json                  ← REPLACES existing
    ├── grade12-photosynthesis-path.json                 ← REPLACES existing
    └── grade8-unreachable-destination-path.json         ← NEW
```

---

## Gap 1 — No prompt text exists for any model call

`06_SKELETON_ENGINE.md` specifies the pipeline. `18_AGENT_MASTER_PROMPT.md`
instructs the implementing agent. Neither specifies what the *models* are told,
and no file in the handoff contains a prompt body.

Five calls are required and none has one:

| Call | Introduced by | Phase |
|---|---|---|
| Path planner | new | 5 |
| Knowledge-type classifier | new | 3 |
| Merge critic | new | 5 |
| Component selector | new (defect fix) | 1 |
| Structural planner | rewritten — steps 6 and 7 removed | 6 |

This matters more than usual because the design's central mechanism is
*converting silent failures into visible ones*, and every one of those
conversions lives in prompt text. The instruction "never drop concepts to meet a
lesson count" in file 18 is addressed to the implementing agent. The path
planner will never see it.

**Added:** `20_PROMPT_PACK.md` — all five prompts, each written against the
specific failure mode it is meant to prevent, each with an output contract and a
self-check.

Two design points in it worth knowing before review:

- The path planner decomposes **backward from the destination, then
  forward-verifies from lesson 1**. This is the anti-dropping mechanism made
  mechanical rather than exhortative. Forward decomposition from a topic stops
  when the list feels long enough; backward decomposition cannot stop early
  without leaving a visible hole.

- The merge critic is explicitly **calibrated against its own safe default**. A
  critic that always returns `keep_separate` provides zero over-fragmentation
  control, which is the risk D4 creates by removing count bounds. It is told to
  expect roughly one adjacent pair in four to warrant review.

Each prompt's self-check has a machine counterpart listed at the end of the
pack. Validate; do not trust.

---

## Gap 2 — Planner output had no schema, so the fixtures drifted

`path-lesson.schema.json` describes the **persisted** form: `concept_id` is a
UUID and `prerequisites` are UUIDs.

The path planner cannot emit that. At plan time concepts are unresolved — that
is the point of `concept_candidate` in `05_PATH_PLANNER.md`. So planner output
is a different shape, and it had no schema at all.

Consequence: both existing fixtures emit a flat `path[]` of
`{title, objective, type}`, which matches neither `05_PATH_PLANNER.md` nor
`path-lesson.schema.json`. The Phase 5 gate currently asserts against a shape
the planner will not produce.

**Added:** `schemas/path-plan.schema.json` — the pre-resolution form.
`concept_candidate.slug` plus slug-based prerequisites, becoming a `PathLesson`
with UUIDs after resolution against the concepts registry.

Two boundaries it makes explicit:

- `prerequisites` are slugs of **earlier lessons in this same path**.
- `external_prerequisites` are capabilities assumed already held, and each must
  appear in `scope_contract.assumed_prerequisites` or `starting_knowledge`.

That split is what makes "no silent prerequisite dropping" checkable. Without it
there is no way to distinguish *taught here*, *assumed*, and *missing*.

---

## Gap 3 — The Phase 5 gate was untestable

Phase 5's gate is "Grade 4/12 fixtures; no silent prerequisite dropping."

Neither existing fixture contains a single prerequisite. A gate asserting that
prerequisites are not dropped cannot be tested against paths that have none.

**Replaced:** both fixtures, now with real prerequisite chains, per-lesson
`must_establish` and `exclusions`, knowledge-type classifications, a nominated
merge review, and a completeness block.

The scope difference between them is now material rather than lexical. Grade 4
teaches five capabilities ending at *why photosynthesis matters*; Grade 12
teaches seven ending at *carbon fixation*, and they share no concept slugs. This
is what D-level grade sensitivity requires: different conceptual scope, not the
same concepts in easier words.

**Added:** `grade8-unreachable-destination-path.json` — a negative fixture.

A destination objective that cannot be reached at the stated grade, for two
distinct reasons: one prerequisite (enzyme action) is absent from
`starting_knowledge`, and one required concept (carbon fixation) is excluded by
the unit's own `must_not_introduce`. The path is internally valid but stops
short.

The planner must populate `prerequisite_risks` with both, set
`reaches_destination: false`, and approval must be blocked.

A positive fixture proves the planner can produce a good path. Only a negative
fixture proves the guard fires — and the guard is the entire justification for
removing count bounds. Without it, "no silent prerequisite dropping" is an
assertion rather than a test.

---

## Validation

All three fixtures validate against `path-plan.schema.json`, with zero duplicate
slugs, zero forward references in prerequisite chains, and zero undeclared
external prerequisites.

Machine checks to build alongside them:

```
no duplicate concept_candidate.slug across the path
every prerequisite resolves to an EARLIER lesson  (no forward refs, no cycles)
every external_prerequisite ∈ assumed_prerequisites ∪ starting_knowledge
no must_not_introduce term appears in any objective or must_establish
prerequisite_risks non-empty  ⇒  reaches_destination false
reaches_destination false     ⇒  path approval blocked
```

---

## One sequencing change recommended

`14_IMPLEMENTATION_PHASES.md` puts the knowledge-type classifier in Phase 3 and
shadow logging in Phase 4, with a single comparison surface.

Log the **classifier separately from the skeleton**, over the same 30 lessons.

If classification is unreliable, skeleton-fit results are uninterpretable — a
poor shape could come from a bad table or a bad classification, and the Phase 4
decision gate cannot distinguish them. One extra column in the shadow record,
reviewed independently.

This does not change the phase order. It changes what Phase 4 records.
