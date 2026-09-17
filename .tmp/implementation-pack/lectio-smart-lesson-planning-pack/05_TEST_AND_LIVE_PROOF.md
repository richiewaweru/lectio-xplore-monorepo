# Test + Live Proof Plan

The implementation is not complete when tests are green. It is complete when we can inspect fresh output and see that the new stages genuinely control the lesson.

## 1. Unit tests

### Flow selection

Test:

- output slot names must come from legal slot catalogue;
- max sections enforced;
- exactly one verification/check-equivalent required;
- objective/scope cannot be rewritten;
- departure rationale required when selected flow materially differs from recommended flow;
- repeated roles receive unique code-owned instance IDs;
- required visual flag survives flow selection.

### Teaching task mode

Test:

- formative response action without approved item is legal;
- assessment response action without approved item is illegal;
- approved source on `task_mode=none` is illegal;
- approved source/action compatibility still fails closed;
- no path-local task can appear without SharedTaskSpec.

### Sourcebook

Test:

- unique entry IDs;
- provenance refs must resolve;
- bindings reference existing teaching blocks;
- sourcebook revision must match Teaching Plan revision;
- quantitative examples can carry machine-checkable values.

### Shared tasks

Test:

- every response-bearing learner action has exactly one shared task;
- no shared task for a passive/null action;
- assessment task preserves approved source IDs;
- action matches response contract;
- Learn/Print mappings both exist or generation fails before fork.

### Writers

Test:

- document writer receives referenced sourcebook content;
- writer is rejected if it changes a declared canonical number/date/label in machine-checkable fixtures;
- interaction writer cannot change SharedTaskSpec answer ownership;
- Print treatment cannot change SharedTaskSpec prompt/answer meaning.

### Coherence

Test deterministic fixtures for:

- numeric contradiction;
- name/date contradiction;
- missing task;
- repeated node IDs;
- task before prerequisite teaching state;
- sourcebook reference drift;
- Print/Learn shared-task mismatch.

## 2. Regression suites

At minimum run the existing suites covering:

```text
tests/core/prompts/
tests/core/policies/
tests/curriculum/
tests/planning/
tests/print_learn/
tests/learn/
tests/reliability/
```

Plus architecture/repo validation commands currently used by the reliability-health pass.

Do not delete tests merely because the contract changed. Rewrite tests whose old assertion encoded the superseded rule, e.g. "every response action must own approved source" → "every assessment action must own approved source; formative action must own shared TaskSpec downstream".

## 3. Planner-only cross-subject proof

Before expensive full generation, run the new flow planner over every fixture in `fixtures/cross-subject-live-matrix.yaml` and save:

```text
objective
knowledge type
recommended flow
selected flow
rationale
teaching arc
learner-action positions
```

Success means the planner is not merely returning the recommendation every time and is not forcing one generic flow across subjects.

## 4. Full fresh generation proof

Generate fresh lessons for at least these three:

1. Mathematics — slope/rate of change.
2. History — compare/evaluate primary-source perspectives.
3. Biology — explain a process/mechanism with a misconception.

For each, generate **both** Print and Learn from the same approved Teaching Plan revision.

Save these evidence artifacts:

```text
01-flow.json
02-teaching-plan.json
03-sourcebook.json
04-shared-tasks.json
05-print-output.json
06-learn-output.json
07-print-coherence.json
08-learn-coherence.json
09-repair-events.json
```

Also save rendered PDF / Learn URL or screenshots where the existing live proof harness supports it.

## 5. Manual quality inspection checklist

Do not score aesthetics yet.

Inspect:

### Journey

- Does the lesson begin in a sensible place for this objective?
- Does each stage make the next stage easier?
- Is the learner asked to act at useful moments rather than only at the end?
- Does support fade appropriately when the objective calls for practice?

### Coherence

- Do examples, tables, figures and tasks agree?
- Are names, dates, values and units stable?
- Is a new example clearly marked as new rather than silently replacing the main example?

### Assessment

- Can the learner answer each task using what has been established by that point?
- Does the final check actually demonstrate the objective?

### Path parity

- Do Print and Learn preserve the same shared task meaning?
- Does Learn add interaction without adding new pedagogy?
- Does Print provide usable response space without changing the task?

## 6. Explicit slope regression

Create a regression fixture modeled on the observed failure:

Canonical sourcebook:

```text
points: (1,4), (3,12)
Δx: 2
Δy: 8
slope: 4
```

Require prose + table + figure/task realization.

The test fails if any realized surface asserts slope `3`, changes one of the canonical points without being a separately named example, or gives an answer key inconsistent with slope `4`.
