# Target Architecture

## 1. The problem being fixed

Lectio currently has strong structural safeguards, but the intelligence arrives slightly too late.

The active flow effectively does this:

```text
objective / scope
      ↓
knowledge type + lesson mode
      ↓
fixed skeleton slots
      ↓
structural plan + question placement
      ↓
approved items
      ↓
Teaching Plan LLM
      ↓
independent node writers
      ↓
Print / Learn
```

The Teaching Plan prompt is already capable of planning a coherent arc, but it is explicitly told that section order is fixed. That means the model cannot choose a better teaching journey when the exact objective crosses knowledge types or benefits from a different sequence.

Then each primitive writer receives a local brief and limited neighbour metadata. A paragraph, table, figure and interaction can each be individually reasonable while disagreeing with one another.

## 2. Target shared pipeline

```text
PATH / UNIT TRUTH
objective
scope
prior knowledge
lesson mode
grade / subject
        │
        ▼
FLOW PLANNER
        │
        │ receives:
        │ - recommended skeleton
        │ - legal slot vocabulary
        │ - hard constraints
        │
        │ chooses the exact lesson journey
        ▼
SELECTED FLOW
ordered semantic slots
        │
        ▼
APPROVED ASSESSMENT GENERATION
formal diagnostic/check items only,
targeted to the selected verification slot(s)
        │
        ▼
TEACHING PLAN
arc
section purpose
teaching blocks
learner actions
misconception use
expected evidence
        │
        ├───────────────┐
        ▼               ▼
LESSON SOURCEBOOK     SHARED TASK SPECS
canonical facts       prompts / items
examples              answer contracts
numbers               expected evidence
stimuli               feedback meaning
        │               │
        └───────┬───────┘
                ▼
        SHARED PLAN PACKAGE
                │
        teacher approval/revision
                │
        ┌───────┴────────┐
        ▼                ▼
      PRINT             LEARN
 document primitives  document primitives
 print treatments     retained interactions
 page layout          feedback / attempts
        │                │
        ▼                ▼
 assembled lesson    assembled lesson
        │                │
        └───────┬────────┘
                ▼
    WHOLE-LESSON COHERENCE REVIEW
    deterministic + LLM semantic review
                │
        targeted repair only
```

## 3. Skeletons become strong recommendations

Do not delete `skeletons.yaml`.

It contains useful pedagogy and should continue to provide:

- knowledge-type classification;
- recommended slot sequence;
- slot purposes;
- typical intents;
- support/differentiation suggestions;
- visual requirements;
- hard safety constraints.

Change the authority model:

```text
OLD
skeleton sequence = exact required section order

TARGET
skeleton sequence = default recommendation
legal slot catalogue + hard rules = closed boundary
LLM = chooses exact sequence for this lesson
```

### Hard constraints remain code-owned

The LLM may not:

- change the objective;
- exceed the maximum number of sections;
- use an unknown slot role;
- duplicate or remove a required final verification/check capability without an equivalent verification step;
- introduce excluded scope;
- remove a required visual teaching job;
- invent path-native components or Print/Learn renderers.

The model can choose a sequence such as:

```text
conceptual slope lesson
orient → observe/contrast → explain → model → guided → check
```

when that is better than the default conceptual skeleton.

It can choose a history flow such as:

```text
orient → inspect evidence → contextualise → contrast → evaluate → check
```

using the legal pedagogical vocabulary.

## 4. Teaching Plan stays the shared pedagogical authority

The Teaching Plan remains path-agnostic.

It should answer:

- what the learner is trying to understand/do;
- the arc of the lesson;
- the purpose of each stage;
- the exact teaching move in each block;
- when the learner acts;
- why the learner acts;
- what evidence of learning is expected;
- what misconceptions are surfaced or repaired.

It must not choose:

- `paragraph`, `table`, `callout`, etc.;
- a Learn interaction component;
- a Print page object/treatment;
- CSS/layout/pagination.

## 5. Separate formative task ownership from formal assessment ownership

Current production effectively says:

```text
response-bearing learner_action
    ⇒ must own approved assessment source
```

That prevents useful formative actions such as prediction, sorting, a tiny calculation, or a quick explanation unless an approved question already exists.

Target:

```text
learner_action
    ├── formative
    │     shared TaskSpec authored from the Teaching Plan
    │     no approved assessment source required
    │
    └── assessment
          approved source required
          approved meaning/answer ownership preserved
```

This is NOT permission for Learn to invent extra interactions.

Every response-bearing task remains shared upstream of the Print/Learn fork.

## 6. Lesson Sourcebook

A Sourcebook is a compact shared content commitment, not another textbook.

It exists to stop independent writers from inventing incompatible local details.

Example:

```yaml
entries:
  - id: example-slope-1
    type: quantitative_example
    purpose: establish constant rate
    facts:
      points: [[1, 4], [3, 12]]
      delta_x: 2
      delta_y: 8
      slope: 4
      units: metres_per_second

  - id: misconception-constant-value
    type: misconception_resolution
    statement: constant slope does not mean constant distance
```

The graph, prose, table and task can all reference `example-slope-1`.

For history, a Sourcebook can hold dates, named sources and claims.
For literature, passage references and character/event facts.
For languages, target sentences and vocabulary.
For science, observations, variables and mechanisms.

## 7. Shared TaskSpec

One shared task is authored once.

Example:

```yaml
id: task-guided-slope-1
teaching_block_id: guided-b1
mode: formative
action: enter-number
prompt: "Find the slope between (2, 8) and (5, 20)."
sourcebook_refs: [example-slope-practice-1]
expected_evidence: "Learner computes change in y divided by change in x."
evaluation:
  type: exact_number
  value: 4
feedback:
  success: "The rate of change is 4 units for each 1 unit of x."
  hint: "Find Δy and Δx before dividing."
```

Then:

```text
PRINT → number/work area using the same prompt
LEARN → numeric interaction using the same prompt/evaluation
```

The path changes the experience, not the teaching task.

## 8. Coherence review

Schema validation is not lesson-quality validation.

Run a whole-lesson reviewer after each full path has been assembled.

The reviewer checks:

- contradictions;
- inconsistent numbers/dates/names/units;
- assessment before instruction;
- repeated explanations;
- missing planned teaching moves;
- examples that do not support the explanation;
- tasks that cannot be answered from lesson state;
- difficulty progression;
- final evidence alignment to the objective;
- sourcebook drift;
- Print/Learn task meaning drift.

It returns precise repair targets.

Never ask the reviewer to rewrite the whole lesson.


## 9. Assessment timing: minimal safe change

This pass does **not** need to throw away the existing approved-item pipeline.

Change its timing/ownership boundary:

```text
OLD
fixed skeleton → question placement/items → Teaching Plan

TARGET
smart selected flow → formal assessment placement/items → Teaching Plan
```

Formal assessment generation remains objective/card-based and source-controlled. It now targets the selected verification/check slot rather than a slot that was fixed before smart planning.

Formative learner tasks are different: they are authored **after** Teaching Plan as SharedTaskSpecs and do not require approved assessment IDs.

This gives Lectio flow-first planning without unnecessarily rewriting the trusted approved-item machinery in the same pass.
