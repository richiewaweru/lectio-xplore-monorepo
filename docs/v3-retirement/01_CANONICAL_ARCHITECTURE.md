# Canonical Architecture Boundary

## The only supported creation spine after this cleanup

```text
                         USER / TEACHER
                               |
                               v
                       Unit + Path Lesson
                               |
                               v
                         PREPARATION
                               |
             +-----------------+-----------------+
             |                                   |
             v                                   v
       Structural Plan                     Source / Items
             |                                   |
             +-----------------+-----------------+
                               |
                               v
                         Teaching Plan
                               |
                         Teacher Gate
                               |
                          APPROVED PLAN
                               |
                               v
                     Native Realization Layer
                               |
                   +-----------+-----------+
                   |                       |
                   v                       v
                 LEARN                   PRINT
                   |                       |
             interactions             treatments/layout
             learner state            page geometry
             feedback                 answer surfaces
             publish/release          pagination/PDF
```

The exact implementation may temporarily retain compatibility adapters during migration, but no new product work may depend on the old V3 execution architecture.

---

## Current native ownership target

The final repository should read roughly like:

```text
application/
  unit_lesson/
    preparation/
    routes/
    realizations/
    retry/

curriculum/
  planning/
    models
    structural_planner
    persistence
    skeletons
    objective_ownership
  items/
    generator
    models
    errors
  teaching_plan/
  lesson_review/
  shared_tasks/

document/
  composer
  writer
  models
  composition

media/
  generation/
    executor
    models
  qc/
  storage/

infra/
  authoring/
    engine
    structured_provider
    model_policy
  execution/
    retries
    checkpoints
    timeouts

learn/
  generation/
  interactions/
  authoring/
  publishing/

print/
  generation/
  rendering/
  export/
```

Exact filenames may differ if the repository already has a more natural current home. **Ownership intent matters more than literal names.**

---

## What must disappear as an architectural concept

The following flow is legacy:

```text
Blueprint
   |
   v
SectionBrief
   |
   v
compile_execution_bundle
   |
   +--> V3 section_writer
   +--> V3 question_writer
   +--> V3 visual lane
   |
   v
GeneratedComponentBlock
   |
   v
legacy pack / section assembly
```

This does not mean every model historically created in V3 is useless. If `StructuralPlan`, visual generation, or item generation became part of the native system, they should survive under current ownership.

---

## The cleanup test

At the end, a new engineer should be able to answer:

> "Where is the current Lectio lesson generated?"

without needing to know V1/V2/V3 history.

A healthy answer should be:

```text
Unit preparation
 -> curriculum planning
 -> Teaching Plan
 -> native realization
 -> Learn / Print
```

not:

```text
Some of it is in v3_blueprint,
some in v3_execution,
some in print/v3_studio,
some in application/unit_lesson,
and some of those V3 files are dead.
```

That reduction in ambiguity is a primary acceptance criterion, not just cosmetic cleanup.
