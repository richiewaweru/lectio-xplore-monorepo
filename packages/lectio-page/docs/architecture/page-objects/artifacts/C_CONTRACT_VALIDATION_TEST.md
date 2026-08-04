# C. Contract Validation Test — Planner Palette Before Renderer Work

## Purpose

This test answers the riskiest question first:

> Does replacing 33 named components with 10 page objects and a rich intent catalogue preserve or improve planning quality?

No renderer work begins until this test passes.

## 1. Test method

Run the current planner and the v2 planner against the same teacher brief, model, temperature, source context, learner groups, and token budget.

Only the palette changes.

### Control

The current `_planner_index_block()` output based on component IDs, section fields, role, cognitive job, limits, and budgets.

### Candidate

The v2 palette in `fixtures/planner-palette-v2.txt`, built from:

- pedagogical intents;
- valid object choices;
- generation guidance;
- structural constraints;
- learner-group differences;
- maximum aside density;
- print-first placement rules.

## 2. Fixed comparison topic

Use `fixtures/planner-comparison-topic.json`.

The topic is deliberately chosen to require:

- an opening phenomenon;
- causal explanation;
- definition;
- process tracing;
- visual representation;
- misconception handling;
- guided practice;
- independent practice;
- assessment;
- summary and forward bridge.

## 3. Candidate planner instruction

```text
Plan the lesson as pedagogical moves expressed through page objects.

Do not choose decorative components.
Choose an intent first, then the simplest valid page object that performs that cognitive job on paper.

The plan must:
- establish the objective;
- preserve a coherent learning sequence;
- vary document form only when it improves learning;
- reserve asides for genuinely set-apart content;
- use no more than two asides in a normal lesson;
- avoid consecutive objects with identical intent unless justified;
- include appropriate learner-group variation;
- specify object, intent, position, content brief and source anchors.
```

## 4. Required output shape

```json
{
  "sections": [
    {
      "id": "section-1",
      "title": "Why the colour spreads",
      "moves": [
        {
          "id": "move-1",
          "position": 0,
          "intent": "orient",
          "object": "prose",
          "brief": "Open with a drop of food colouring spreading in still water.",
          "must_establish": [],
          "must_not_introduce": ["diffusion equation"],
          "learner_adaptation": {
            "support": "concrete short sentences",
            "core": "standard",
            "extension": "ask for mechanism prediction"
          }
        }
      ]
    }
  ]
}
```

## 5. Scoring rubric

Score both plans 0–2 on each criterion.

| Criterion | 0 | 1 | 2 |
|---|---|---|---|
| Objective coverage | major gap | mostly covered | fully covered |
| Cognitive progression | incoherent | partially sequenced | deliberate progression |
| Intent richness | repetitive/bland | adequate | varied for pedagogical reasons |
| Object restraint | decorative or boxed | some unnecessary variety | simplest valid forms |
| Misconception handling | absent | generic warning | targeted diagnosis and correction |
| Practice progression | absent | one practice mode | guided → independent → check |
| Visual purpose | decorative | relevant | indispensable and specified |
| Differentiation | cosmetic | some scaffolding | structural adaptation |
| Print plausibility | screen-like | mixed | clearly paper-native |
| Plan specificity | vague | usable | implementation-ready |

Maximum: 20.

## 6. Binary gate

The v2 palette passes only if:

- total score is at least 16/20;
- it is not more than one point worse than the control on objective coverage;
- it equals or beats the control on cognitive progression;
- it uses at least 8 distinct intents in a multi-section lesson where justified;
- it uses at least 4 object types;
- it uses no more than 2 asides unless the planner provides a specific reason;
- no object name is used as a pedagogical rationale;
- support/core/extension differences alter structure or scaffolding, not color or labels;
- the output validates against the plan schema.

## 7. Failure signatures

The test fails when:

1. Every section becomes `prose + questions`.
2. The planner uses only 8–12 broad intents.
3. Intents merely rename old components.
4. The planner chooses `aside` for every important statement.
5. Object choice is justified by appearance rather than cognitive work.
6. Differentiation changes only word count or reading level.
7. The plan omits position.
8. The plan cannot express two blocks of the same object type.
9. The planner invents screen interactions.
10. Required teaching moves disappear because their old component names disappeared.

## 8. Review protocol

Run three seeds per planner. Review blinded where possible.

Record:

- raw outputs;
- validation errors;
- scores by criterion;
- intent frequency;
- object frequency;
- aside count;
- duplicate object count;
- reviewer notes.

Do not average away catastrophic failures. Any output below 12/20 is investigated separately.

## 9. Decision

- **Pass:** begin page-object implementation.
- **Revise:** adjust intent catalogue and rerun.
- **Fail:** stop. Do not build the renderer merely because the schema is elegant.

**DOCUMENT VERSION:** 1.0  
**DEPENDS ON:** B and planner fixture
