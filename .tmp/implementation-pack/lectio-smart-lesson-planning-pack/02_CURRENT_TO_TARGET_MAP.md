# Current → Target Map

Baseline: `main@af7a3d46e684d9752c6e18034f9b86b322348936`

## Current strengths to preserve

| Current capability | Keep? | Target use |
|---|---:|---|
| Path objective ownership | Yes | Remains immutable truth |
| `skeletons.yaml` | Yes | Recommended flows + hard pedagogical metadata |
| Teaching Plan `arc` | Yes | Whole-lesson instructional commitment |
| Teaching Plan sections/blocks/transitions | Yes | Main shared lesson journey |
| Closed learner-action vocabulary | Yes | Path-agnostic semantic action |
| Teaching revision + approval gate | Yes | Teacher approves the shared lesson plan/package |
| Shared document primitives | Yes | Ordinary content realization |
| Learn interaction shortlist | Yes | Representation only |
| Print task treatments | Yes | Paper representation only |
| Checkpoints/call budgets | Yes | All new authoring stages must participate |

## Current constraint 1 — fixed section order

Current files:

- `backend/src/v3_blueprint/skeletons.py`
- `backend/resources/skeletons.yaml`
- `backend/src/application/unit_lesson/prepare.py`
- `backend/resources/path-structural-planner-v1.txt`

Current behavior:

- code selects a skeleton;
- the planner receives `slots[]` as fixed;
- `_build_structural_plan` rejects output whose roles differ from the exact skeleton sequence.

Target:

- produce a `recommended_slots` sequence from skeletons;
- expose a **closed legal slot catalogue** and hard constraints;
- planner chooses `selected_slots` for the exact lesson;
- code validates legality, max count, verification coverage and required flags;
- planner must justify meaningful departure from recommendation.

## Current constraint 2 — response tasks require approved sources

Current files:

- `backend/src/print/generation/whole_lesson/teaching_agent.py`
- `backend/resources/prompts/learner-action-policy.md`
- `backend/src/curriculum/teaching_plan/models.py`

Current behavior:

- `_task_source_contract_errors` rejects response-bearing learner actions without approved source ownership.

Target:

Add task mode:

```text
none | formative | assessment
```

Rules:

- `none`: no response-bearing action.
- `formative`: response-bearing action allowed without approved source; shared TaskSpec is authored after Teaching Plan.
- `assessment`: response-bearing action requires approved source; source meaning is immutable.

No path may create a response task that does not exist in the shared task registry.

## Current constraint 3 — primitive writers can invent local facts

Current files:

- `backend/src/document/writer.py`
- `backend/resources/prompts/document-writer.md`
- `backend/src/learn/generation/native_production.py`
- Print shared writer bridge / native production

Current behavior:

- each node receives lesson context, allowed facts and neighbour summaries;
- the completed content of adjacent nodes is not a strong canonical source;
- numerical examples and contextual details may drift.

Target:

Add `LessonSourcebook` and require writers to receive exact referenced entries.

For any concrete value/fact/stimulus that has a sourcebook ref:

- copy it exactly;
- do not replace it with a locally invented variant;
- do not create a second example unless the Teaching Plan requested a second example.

## Current constraint 4 — Learn interaction writer authors task content locally

Current files:

- `backend/src/learn/generation/interaction_writer.py`
- `backend/resources/prompts/interaction-writer.md`

Target:

Interaction writer becomes mostly a **realizer** of `SharedTaskSpec`.

It may adapt wording only where the interaction schema requires it; it must not change:

- prompt meaning;
- answer/evaluation contract;
- item set;
- sourcebook values;
- difficulty;
- purpose.

## Current constraint 5 — no active whole-lesson semantic gate after writing

Current validation is strong at plan/schema legality.

Target:

Add:

```text
curriculum/lesson_review/
  models.py
  deterministic.py
  reviewer.py
  repair.py
```

or equivalent shared ownership outside Print/Learn.

Run the same review contract over both assembled path outputs.

## Prompts that change

### Replace / version-bump

- `path-structural-planner-v1.txt` → smart flow version.
- `lesson-approach-planner-v2.txt` → v3.
- `learner-action-policy.md` → v2.
- `document-writer.md` → v2.
- `interaction-writer.md` → v2.
- `print-realization.md` → v2.

### New

- `lesson-sourcebook-writer.md`
- `shared-task-writer.md`
- `whole-lesson-coherence-reviewer.md`
- `targeted-lesson-repair.md`

### No semantic change required in this pass

- `document-composer.md`: already chooses structure inside a closed per-block allowlist.
- `interaction-selection.md`: already chooses a Learn representation inside a closed shortlist without changing pedagogical meaning.

Version/hash tests must still be updated if manifest versions change.


## Assessment generation sequencing

Do not expand this pass into a full replacement of the approved-item subsystem.

Move/ensure sequencing so that:

```text
smart flow selected
      ↓
formal assessment slot known
      ↓
approved formal item generation
      ↓
Teaching Plan binds assessment source
      ↓
formative SharedTaskSpecs authored later
```

This preserves the current strict approved assessment contract while removing the reason ordinary formative actions had to masquerade as approved assessment items.
