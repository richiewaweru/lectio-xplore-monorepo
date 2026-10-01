# Target Architecture

## Canonical product spine

```text
                       TEACHER / AUTHOR
                             │
                             ▼
                      Unit / PathLesson
                             │
                             ▼
                        PREPARATION
                             │
                ┌────────────┴────────────┐
                ▼                         ▼
         Structural Plan            Sources / Items
                └────────────┬────────────┘
                             ▼
                   Enriched Teaching Plan
                             │
                       Teacher Approval
                             ▼
                     APPROVED PLAN
                     revision + hash
                             │
                             ▼
               ┌────────────────────────┐
               │ SHARED DOCUMENT RUN    │
               │ section composition    │
               │ parallel writers       │
               │ section validation     │
               │ continuity validation  │
               │ document QA            │
               └───────────┬────────────┘
                           ▼
                 SharedLessonDocument
                    revision + hash
                           │
                 ┌─────────┴─────────┐
                 ▼                   ▼
              LEARN RUN           PRINT RUN
                 │                   │
           interactions          treatments
           runtime UX            page/layout
                 ▼                   ▼
           LearnDocument        PrintDocument
                 ▼                   ▼
              Publish               PDF
```

## Ownership

**Teaching Plan:** pedagogy, progression, continuity, learner action, evidence, misconceptions and state transitions.

**SharedLessonDocument:** exact learner-facing ordinary lesson structure/content and TaskAnchor positions.

**Learn:** interactive affordance, feedback, attempts, progress, navigation and publishing.

**Print:** paper task treatments, response surfaces, page geometry, pagination, answer key and PDF.

## Dependency direction

```text
application/orchestration
        ↓
curriculum + document
        ↓
shared artifact
     ┌──┴──┐
   learn  print

all domains may depend on infra;
infra must not depend on product-domain logic.
```

`document/` must never import `learn/` or `print/`.
