# Path Planner Specification

## Responsibility

Produce a complete, ordered set of assessable capabilities for the requested topic and learner stage.

It does not:

- write lesson prose;
- choose components;
- generate items;
- create variants;
- obey a requested lesson count by dropping concepts;
- create teaching periods.

## Inputs

Required:

- topic;
- subject;
- grade/learner stage;
- destination objective;
- starting knowledge;
- curriculum context if available.

Optional:

- must include;
- must avoid;
- terminology;
- notation;
- assessment context;
- known difficulties.

## Output

```json
{
  "scope_contract": {},
  "modules": [
    {
      "title": "Energy transfer",
      "lessons": [
        {
          "concept_candidate": {},
          "objective": "Explain how light energy drives electron transfer.",
          "prerequisites": [],
          "must_establish": [],
          "exclusions": [],
          "primary_knowledge_type": "conceptual",
          "secondary_demand": null,
          "merge_warning": false
        }
      ]
    }
  ],
  "adjacent_merge_reviews": []
}
```

## Assessability rule

A lesson is one independently assessable capability.

Use:

> Can a diagnostic item test A without requiring B?

- yes → separate;
- no → same capability;
- relationship itself is objective → paired relation is one capability.

## No hard count bound

The planner produces all concepts inside the scope contract.

The UI reports:

- concept count;
- likely teaching periods;
- high-priority concepts;
- optional concepts;
- prerequisite risks.

The teacher can skip or defer explicitly.

## Over-fragmentation control

For every adjacent pair, run a merge critic:

```text
Could these be taught and assessed as one capability
without losing diagnostic clarity?
```

Return:

- keep separate;
- merge suggested;
- teacher decision required.

## Grade-level validation

Same topic must produce materially different conceptual scope by grade.

Required fixtures:

- Grade 4 photosynthesis;
- Grade 12 photosynthesis.

## Objective authority

Path objective is immutable downstream unless teacher approves an explicit patch.

## Replanning

Selective replan must preserve:

- teacher-authored lessons;
- concept IDs;
- approved objectives unless selected;
- generated packs unless invalidated explicitly.

## Silent-failure checks

Reject or flag:

- missing prerequisite chains;
- advanced concepts outside scope;
- duplicate capabilities under different names;
- a path that does not satisfy final evidence;
- factual fragments likely too thin;
- circular dependencies;
- overly broad objectives.
