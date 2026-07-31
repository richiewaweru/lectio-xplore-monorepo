# Product Specification

## Primary user

A teacher planning and delivering a topic to a mixed classroom.

## Core job

> “Show me the complete conceptual route for this topic at this level, let me review it, prepare one reliable concept lesson at a time, create controlled support and extension versions, and print or compose what I need.”

## Core experience

```text
Create unit
  ↓
Review scope
  ↓
Review concept path
  ↓
Group concepts into teaching periods
  ↓
Select one concept lesson
  ↓
Preview lesson shape
  ↓
Review concept card and misconceptions
  ↓
Generate controlled variants
  ↓
Review / repair / approve
  ↓
Compose resources
  ↓
Print / teach
  ↓
Enter shared diagnostic marks
  ↓
Record actual outcome
```

## Three separate structures

Do not conflate them:

```text
Concept Path
= what must be learned, in dependency order

Teaching Schedule
= how concepts are grouped into periods

Generated Resources
= lesson/booklet/homework/quiz/revision projections
```

## Product nouns

Teacher-facing:

- Unit
- Concept Path
- Concept
- Teaching Period
- Lesson Shape
- Version
- Shared Check
- Resource
- Results

Internal:

- ConceptCard
- StructuralPlan
- Skeleton
- Slot
- Pack
- Generation
- Document

## Product promise over a general LLM

A general LLM can generate three worksheets. This platform preserves:

- stable concept identity;
- complete prerequisite-aware scope;
- path continuity;
- approved objectives;
- predictable lesson shapes;
- explicit variation;
- common diagnostics;
- provenance;
- reusable projections;
- outcome records.

## Product boundaries

Product A does not include:

- learner accounts;
- adaptive routing;
- knowledge tracing;
- autonomous tutoring;
- experiment assignment;
- marketplace.

A single teacher marks-entry surface is included because it converts misconception-tagged distractors into evidence.
