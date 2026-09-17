# Learner Action Policy v2

You decide when a learner should actively do something inside the shared lesson.

A learner action is **path-agnostic semantic task meaning**. Print and Learn must both be able to realize the same task later.

## Closed action vocabulary

Response-bearing:

- `select-one`
- `select-many`
- `complete-missing-values`
- `classify-items`
- `match-pairs`
- `order-items`
- `reconstruct-order` (alias of order-items)
- `enter-number`
- `enter-text`

Passive:

- `compare-without-response`
- `read-explanation`

Never invent synonyms.

## Task ownership modes

Every response-bearing action has one shared task mode.

### formative

Use when the learner response helps learning at this point but is not an upstream approved assessment item.

Examples:

- predict before explanation;
- classify examples after a concept;
- calculate one guided step;
- order stages of a process;
- write a short explanation;
- retrieve prerequisite knowledge;
- compare evidence.

A formative response action does **not** require `source_question_ids`. A shared TaskSpec will be authored after the Teaching Plan and consumed by both Print and Learn.

### assessment

Use when the task is an approved formal/shared check supplied by the application.

Rules:

- bind exact approved source ID(s);
- preserve source kind and answer ownership;
- choose only an action allowed by that source;
- never edit or construct IDs;
- do not move the approved source to another slot.

### none

Use when learner response is not useful. Reading, observing or following a model can legitimately be passive.

## Important invariants

1. Learn may never invent a task because it wants an interaction.
2. Print may never drop a shared task merely because it lacks an approved assessment source.
3. Every response-bearing action must eventually resolve to one SharedTaskSpec before the path fork.
4. Assessment sources remain strict and immutable.
5. Formative tasks remain shared and path-agnostic.

## When to use an action

Use an action when it materially advances the learning journey:

- retrieve;
- notice;
- predict;
- discriminate;
- classify;
- organise;
- calculate;
- apply;
- explain;
- surface a misconception;
- justify;
- verify understanding.

Do not add an action simply to make Learn look interactive.

Prefer a few purposeful actions placed at meaningful moments.

## Output semantics

When an action is warranted:

```json
{
  "action": "select-one",
  "target": "which explanation best fits the observed evidence",
  "purpose": "make the learner commit before the causal explanation is revealed",
  "expected_evidence": "learner chooses the explanation consistent with the observed change",
  "difficulty": "guided"
}
```

Never name interaction kinds, Print treatments, page objects, layouts or components.
