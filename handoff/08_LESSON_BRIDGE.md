# Path Lesson to Xplore Bridge

## Goal

Reuse existing Xplore planning, review, item, variant, QC, Builder, and print systems.

## Input bundle

```python
PrepareLessonRequest:
    unit_id
    path_version_id
    path_lesson_id
    group_ids[]
    lesson_mode
```

Bridge resolves:

- UnitScopeContract;
- approved PathLesson objective;
- prerequisites;
- preceding planned establishment;
- LessonActual records;
- concept ID;
- knowledge type;
- selected skeleton;
- unit groups;
- terminology and notation.

## New planning split

The current structural planner must no longer decide:

- objective;
- section count;
- section sequence;
- role names;
- broad scope;
- group structural differences.

It still decides:

- anchor/example;
- misconception drafts where not approved;
- components within slots;
- visual use within constraints;
- question placement consistent with locked check;
- prose-writing briefs.

## Output adaptation

Create a single-card StructuralPlan compatible with current execution:

```text
PathLesson objective
Skeleton slots
  ↓
SectionPlan[]
  ↓
ConceptCard exactly one
  ↓
Existing approval halt
```

## Card identity

The ConceptCard references canonical `concept_id`.

Its local ID may remain a slug for compatibility, but provenance stores canonical UUID.

## Idempotency

Preparing the same path-lesson revision twice:

- returns existing pack if compatible;
- requires explicit regenerate if invalidated;
- never creates duplicate item sets silently.

## Legacy

Existing Studio generation remains unchanged behind legacy route/feature section.

Existing pack can be wrapped as:

```text
Legacy Unit
  └── one PathLesson
       └── existing pack
```

No destructive migration.
