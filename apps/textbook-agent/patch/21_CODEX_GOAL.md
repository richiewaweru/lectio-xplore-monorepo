# GOAL — Xplore Learning Platform V2

You are running a long task. It will span many sessions and will be interrupted.
Read this document fully before touching code, and re-read `PROGRESS.md` at the
start of every session.

---

## 0. The terminal state

You are **done** when all of the following are true, and not before:

```
Phase 0  baseline captured and reproducible
Phase 1  four silent defects fixed, each with a regression test that FAILED first
Phase 2  concepts table, provenance, objective ownership — generation unchanged
Phase 3  skeletons.yaml loaded, classifier live, preview endpoint live — output unchanged
Phase 4  shadow logging live and PROVEN on ≥3 real generations; review surface exists
Phase 5  path planner + units backend, validating against all three fixtures
         including the negative one
         → HALT. Write the handoff report. Do not proceed.
```

**Phase 6 and beyond require a human decision you cannot make.** Skeleton
authority is granted only after a human reviews ~30 real shadow-logged lessons.
You will build the machinery for that study and stop. Stopping at that gate is
success, not incompleteness.

If you find yourself about to promote skeletons to authority, build path UI, or
mark Phase 4 complete with fewer than 30 human-reviewed lessons — stop and
re-read this section.

---

## 1. Read before writing

In this order:

```
handoff/00_DECISION_RECORD.md          D1–D13. These are settled. Do not relitigate.
handoff/02_CURRENT_SYSTEM_AND_DEFECTS.md
handoff/14_IMPLEMENTATION_PHASES.md
handoff/17_RISKS_NON_GOALS_STOP_RULES.md
patch/PATCH_NOTES.md                   what the patch adds and why
patch/20_PROMPT_PACK.md                the five model prompts — verbatim source
patch/schemas/path-plan.schema.json
handoff/source_material/skeletons-v1-draft.yaml
```

Then read the actual repository. Every claim in the handoff about current code
must be verified with `grep` before you rely on it. Where handoff and code
disagree, **the code is the truth** — record the contradiction in `PROGRESS.md`
and proceed from what the code does.

Repository: `richiewaweru/text-book-generator`
Base branch: `xplore`. Reference: `v3`.
Work on a new branch `v2-platform`. Never force-push. Never rewrite history.

---

## 2. Invariants — breaking any of these is a failed run

Verified present in the current code. Preserve all of them:

```
1  item generation receives ONE ConceptCard plus three scalars via private attrs.
   It must not import section, component, brief, or generated-content types.
   There is a test asserting this. It must keep passing.

2  items are pack-owned, not variant-owned. Every group gets the same quiz.

3  QC verdicts are RECOMPUTED from checks; a model-stated verdict that
   disagrees raises.

4  distractors may carry a null misconception tag. Never force-map.

5  sibling variant failure does not block sibling variants.

6  teacher edits survive regeneration (preserve-and-flag).

7  awaiting_review survives process restart.

8  Lectio contracts, the Builder, and PDF generation keep working.

9  StructuralPlan.max_six_sections stays enforced.
```

Before each commit, confirm 1–9 still hold. If a change requires breaking one,
**stop and report**. Do not negotiate with yourself.

---

## 3. What counts as evidence

A phase is complete when you can paste the command and its real output. Not a
summary. Not "tests pass."

```
✗  "Added the concepts table and tests pass."
✓  $ pytest backend/tests/test_concepts.py -q
   14 passed in 2.31s
   $ alembic upgrade head && alembic downgrade -1 && alembic upgrade head
   [output]
```

For every defect fix in Phase 1, you must show the test **failing before the
fix** and **passing after**. A test written after the fix proves nothing about
the defect.

Never weaken an assertion to make a test pass. If a test is wrong, say why in
`PROGRESS.md` and change it deliberately, in its own commit.

---

## 4. Phases

### Phase 0 — Baseline

```
capture the xplore HEAD sha
run: backend test suite, architecture gate, frontend build
record which currently fail  (the frontend harness is known to stall on Windows;
  record the exact symptom, do not fix it now)
save one current generation end-to-end as a fixture for later comparison
write RUNBOOK.md with the exact commands you used
```

**Gate:** you can re-run everything from `RUNBOOK.md` in a clean checkout.

---

### Phase 1 — Fix the four silent defects

Each defect below is real and verified. Write the failing test first.

**1.1 — Dead role validation.**
`_allowed_roles_from_resource_spec()` reads `required_roles` / `optional_roles` /
`sections[].role`. The active spec `backend/contracts/guided-concept-path.json`
has none of these, so the returned set is empty and validation is skipped
entirely. Meanwhile the planner prompt tells the model to use "the exact role
strings allowed by the active resource spec."

Fix: roles come from `skeletons.yaml` slot ids. Validate against that. If the
skeleton system is not yet loaded (it arrives in Phase 3), emit an explicit
warning rather than silently passing — a temporary loud failure is correct here.

**1.2 — `cognitive_job` never reaches the planner.**
All 30 components in `component-registry.json` carry a distinct `cognitive_job`.
It is passed to the section writer. The component-choosing step does not receive
it.

Fix: pass the registry entries — slug, `cognitive_job`, `section_field` — to
whichever call selects components.

**1.3 — `StructuralPlan` is `extra="ignore"`.**
Relaxed to tolerate a legacy top-level `voice` field.

Fix: restore `extra="forbid"`. Add an explicit legacy adapter that maps the old
field and **logs** when it fires. Silent acceptance of unknown keys is the
defect; a loud, tested adapter is the fix.

**1.4 — Misconception quota.**
The current prompt demands 2–4 per card, which manufactures fiction on
recall-heavy objectives.

Fix: 0–3, gated on the confident-wrong-answer test. Apply to new path lessons
only; legacy packs keep rendering.

**Gate:** four regression tests, each shown failing before and passing after.
All legacy fixtures still load. All nine invariants hold.

---

### Phase 2 — Irreversible foundations

These are cheap now and expensive later. They change no behaviour.

```
concepts table          canonical_slug, subject, title, canonical_description
                        per schemas/concept.schema.json
concept references      path lessons and cards reference concept ids
objective ownership     D2. hash the path objective, carry the hash, compare
                        after generation. Silent rewriting must become
                        impossible, not merely forbidden.
provenance fields       skeleton_id, skeleton_version, knowledge_type,
                        knowledge_type_source, toggles_applied[],
                        deviations_applied[]  — nullable for now
```

**Gate:** run the Phase 0 saved generation. Byte-for-byte identical output, or a
documented and justified difference. Migrations up, down, and up again.

---

### Phase 3 — Skeleton data and preview

```
install skeletons-v1-draft.yaml as skeletons.yaml, versioned, loaded at startup
validate on load: every base skeleton ≤5 slots, expansion ≤6, check present
                  and locked, every slot's components exist in the registry
knowledge-type classifier  → use §2 of 20_PROMPT_PACK.md VERBATIM
skeleton preview endpoint  → POST /skeletons:preview, zero model calls
deviation request schema
```

The classifier prompt is a specification. Do not paraphrase, shorten, or
"improve" it. If you believe it is wrong, record that in `PROGRESS.md` and use
it anyway — it is under separate review.

**Gate:** zero output change to any existing path. Preview returns a slot list
for all 11 skeletons. Classifier returns valid enum values on the objectives in
all three fixtures.

---

### Phase 4 — Shadow logging

Build the machinery. Do not run the study — you cannot.

```
on every lesson generation, ALSO compute what the skeleton would have produced
log SkeletonShadowRecord per 06_SKELETON_ENGINE.md
log the CLASSIFIER separately, as its own reviewable column
   (if classification is unreliable, skeleton-fit results are uninterpretable —
    a bad shape could come from a bad table or a bad classification, and the
    gate cannot distinguish them)
build the reviewer surface or CSV export
```

**Gate:** shadow records written for at least 3 real generations, pasted in full.
No output change. Then **stop advancing the study** and note in `PROGRESS.md`
that 30 human-reviewed lessons are required before Phase 6.

---

### Phase 5 — Units and path backend

```
units, scope contracts, path versions
path planner              → use §1 of 20_PROMPT_PACK.md VERBATIM
merge critic              → use §3 of 20_PROMPT_PACK.md VERBATIM
component selector        → use §4 of 20_PROMPT_PACK.md VERBATIM
structural planner rewrite→ use §5 of 20_PROMPT_PACK.md VERBATIM
concept resolution: candidate slug → canonical concept id
operations: split, merge, skip (state, never delete), reorder, replan, approve
NO lesson-count or duration input reaches the planner
bridge: POST /units/{id}/path/lessons/{lid}:prepare → existing pipeline
```

Machine checks that must exist and must be tested:

```
no duplicate concept_candidate.slug across a path
every prerequisite resolves to an EARLIER lesson  (no forward refs, no cycles)
every external_prerequisite ∈ assumed_prerequisites ∪ starting_knowledge
no must_not_introduce term appears in any objective or must_establish
prerequisite_risks non-empty  ⇒  reaches_destination false
reaches_destination false     ⇒  path approval BLOCKED
sections[].role sequence == slots[] exactly
objective hash matches the path objective after generation
```

**Gate — all three must pass:**

```
1  grade4  fixture validates against path-plan.schema.json and all machine checks
2  grade12 fixture likewise, AND shares no concept slug with grade4
   (different conceptual scope, not the same concepts in easier words)
3  grade8-unreachable NEGATIVE fixture: planner populates prerequisite_risks,
   sets reaches_destination false, and approval is BLOCKED
```

Gate 3 is the important one. A positive fixture proves the planner can produce a
good path. Only the negative fixture proves the guard fires — and that guard is
the entire justification for removing count bounds.

**Then halt.**

---

## 5. Working protocol

Every session:

```
1  read PROGRESS.md
2  confirm current phase and what is verified
3  run the phase's gate before assuming prior work still holds
4  work
5  update PROGRESS.md before the session ends — even mid-phase
```

`PROGRESS.md` keeps:

```
current phase and status
per phase: gate result, evidence (real command output), commit sha
contradictions found between handoff and code
decisions taken that were not in the handoff, with reasons
open questions for the human
anything deliberately deferred
```

Commit per logical change, message prefixed `P{n}:`. Never bundle a defect fix
with a feature. Never commit with a failing gate.

---

## 6. Stop and ask

Halt and write the question in `PROGRESS.md` when:

```
an invariant in §2 cannot be preserved
the handoff contradicts itself in a way the code cannot settle
a gate fails twice for the same reason
a fix would require changing a D1–D13 decision
you are about to weaken a test to make it pass
you reach the end of Phase 5
```

Stopping with a clear question is a good outcome. Guessing is not.

---

## 7. Failure modes specific to this task

You will be tempted by each of these. Do not.

```
✗ generating synthetic shadow records to "complete" Phase 4
    the study needs real lessons and human review. 3 real records, then stop.

✗ paraphrasing the prompts in 20_PROMPT_PACK.md
    they are written against specific failure modes. The backward-decomposition
    procedure in §1 and the calibration target in §3 look like verbosity and are
    the mechanism.

✗ marking a phase complete because code exists
    a phase is complete when its gate passes with pasted evidence.

✗ making the negative fixture pass by relaxing the check
    it must fail approval. That is the test.

✗ letting the path planner see a lesson count or duration
    D4. A count target does not create economy; it makes the planner drop
    prerequisites silently.

✗ letting the lesson planner rewrite the objective
    D2. The hash comparison exists to make this impossible.

✗ "improving" a skeleton because a lesson looked odd
    skeletons change through the deviation log, not by intuition.

✗ deleting a skipped path lesson
    skip is a state. The prerequisite chain must still see it.

✗ proceeding past Phase 5
    Phase 6 needs a human decision.
```

---

## 8. Final report

When you halt at the end of Phase 5, produce:

```
1  architecture summary — what exists now that did not before
2  every file added or changed, and every migration
3  gate results for phases 0–5, with real command output
4  the three fixture results, negative fixture called out explicitly
5  invariant check: all nine, confirmed
6  contradictions found between handoff and code
7  decisions you took that the handoff did not cover
8  what the human must now do:
     - run ~30 real lessons with shadow logging on
     - review classifier accuracy INDEPENDENTLY of skeleton fit
     - decide: promote skeletons / revise taxonomy / stop
9  remaining risks
10 work deliberately deferred, and why
```

---

## 9. The one-line version

Fix four silent defects, lay three irreversible foundations, build the skeleton
and path machinery behind gates, prove the negative fixture blocks approval, and
stop at the human decision point with evidence rather than claims.
