# Implementation Phases

This should be implemented as one branch, but each phase has an acceptance gate. Do not continue if a gate fails.

## Phase A — Make skeletons advisory and flow selection smart

### Change

1. Keep skeleton selection as a recommendation source.
2. Build planner input containing:
   - objective;
   - subject / grade;
   - knowledge type;
   - lesson mode;
   - scope / prior knowledge;
   - misconceptions if already known;
   - recommended slot sequence;
   - legal slot catalogue with purpose;
   - max section count;
   - hard requirements such as exactly one final verification capability.
3. Let the structural/flow planner return the selected ordered slot roles.
4. Mint stable slot instance IDs in code after the model returns roles.
5. Replace exact-equality-to-skeleton validation with closed-set structural validation.

### Do not

- let the model invent slot names;
- let it change objective/scope;
- let it choose components;
- remove skeletons.yaml;
- let it exceed max sections.

### Assessment handoff

After the selected flow is valid, build the structural question plan / approved formal assessment items against the selected verification/check slot(s). Do not generate formative practice questions here.

The existing approved-item machinery can remain source-controlled; the important change is that flow selection happens first.

### Gate

Across the cross-subject fixture matrix, the flow planner produces legal but meaningfully different sequences where objectives demand them, and formal question placement references the selected flow rather than the old fixed recommendation.

## Phase B — Strengthen Teaching Plan and task semantics

### Change

Extend TeachingPlanBlock with a path-agnostic task mode, e.g.:

```python
task_mode: Literal["none", "formative", "assessment"] = "none"
```

Optional additional field:

```python
sourcebook_needs: list[str] = []
```

Rules:

- response-bearing `learner_action` + `formative` does not require approved source ownership;
- response-bearing `learner_action` + `assessment` does;
- any approved source implies `assessment`;
- passive blocks may remain `none`;
- task meaning remains shared before fork.

Update hard validators and prompt policy.

### Gate

A Teaching Plan can legally contain a prediction or guided practice task with no approved item while still forbidding a path-local response task.

## Phase C — Shared Lesson Sourcebook

### New artifact

Create one sourcebook per approved Teaching Plan revision.

Minimum entries:

```text
id
type
purpose
content/facts
provenance_refs
```

Useful entry types:

```text
definition
quantitative_example
worked_example_data
scenario
source_excerpt_ref
comparison_case
fact_set
sequence
misconception_resolution
stimulus
```

Do not force every lesson to have every type.

### Behavior

- sourcebook writer sees Teaching Plan + immutable lesson packet;
- it resolves concrete examples/data needed by blocks;
- code validates unique IDs and provenance refs;
- blocks/tasks store refs to sourcebook entries;
- all downstream writers receive the exact referenced entries.

### Gate

A slope graph/table/prose example can be generated from one shared example entry and retains identical points/slope/units.

## Phase D — Shared TaskSpecs

### New artifact

Author one shared task record for every response-bearing learner action.

TaskSpec must be usable by both paths.

Assessment tasks preserve approved item ownership. Formative tasks are authored from Teaching Plan + Sourcebook.

### Gate

For each response task:

```text
Teaching block id
Shared task id
Print treatment
Learn interaction
```

can be traced end-to-end, and both paths preserve the same prompt/answer meaning.

## Phase E — Make writers sourcebook-bound

### Document writer

Pass:

- exact sourcebook entries for the block;
- exact shared task summary where relevant;
- previously committed neighbouring node summaries/content where safe;
- objective / terminology / exclusions.

The writer must not invent a conflicting replacement example.

### Learn

Interaction writer consumes SharedTaskSpec rather than inventing an independent question.

### Print

Print realization consumes SharedTaskSpec and maps it to paper treatment. It may decide response space/layout only.

### Gate

No path-owned writer changes a shared task's values, choices, correct answer, or purpose.

## Phase F — Whole-lesson coherence review + targeted repair

### New review stage

After a full Print or Learn lesson is assembled:

1. deterministic checks;
2. one LLM semantic review;
3. if needed, targeted repair of named nodes/tasks only;
4. re-run checks;
5. cap repairs.

### Deterministic checks

At minimum:

- all Teaching Plan blocks represented as required;
- all response-bearing task blocks have a shared task id;
- no unknown sourcebook refs;
- sourcebook constants copied consistently where machine-readable;
- no duplicate node/task IDs;
- assessment answer ownership preserved;
- Print and Learn task registries match the same shared tasks.

### LLM checks

- contradiction;
- pacing;
- unnecessary repetition;
- untaught assessment;
- confusing transitions;
- example/explanation mismatch;
- task answerability;
- objective evidence.

### Gate

Reviewer emits `pass` or a small list of repair targets. It never returns a rewritten lesson.

## Phase G — Persistence / observability

Persist and expose in generation state:

```text
selected_flow
teaching_plan
lesson_sourcebook
shared_tasks
print_coherence_report
learn_coherence_report
repair_events
```

Every artifact should record the Teaching Plan revision/hash it belongs to.

If Teaching Plan changes, invalidate sourcebook/tasks/path outputs built from the old revision.

### Gate

Reloading a generation shows exact artifacts and revision lineage.

## Phase H — Cross-subject tests and live proofs

Run the matrix in `fixtures/cross-subject-live-matrix.yaml`.

Do not judge UI polish in this pass.

The purpose is to answer:

> Does Lectio now produce a coherent teaching journey and internally consistent lesson across subjects, in both Print and Learn?
