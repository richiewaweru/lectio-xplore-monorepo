# Generic Generation Runtime

## Goal

Replace path-specific lifecycle logic with one operational model used across preparation, SharedDocument, Learn, Print, publish and PDF.

## Hierarchy

```text
GenerationBuild
 ├─ PreparationRun
 ├─ SharedDocumentRun
 ├─ LearnRun
 ├─ PrintRun
 ├─ PublishRun
 └─ PdfRun
```

Run = durable artifact-producing operation.
Work item = durable unit inside a run.

Example SharedDocument work items:

```text
compose:orient
write:orient
compose:explain
write:explain
media:figure-1
continuity:orient->explain
document-qa
```

## Universal statuses

```text
queued
running
awaiting_review
ready
failed_recoverable
failed_terminal
cancelled
```

Activities such as `writing` or error names are not statuses.

## Stage is separate

Examples: structural_planning, teaching_planning, section_composition, section_writing, media_generation, continuity_validation, document_qa, learn_realization, print_realization, pdf_render, publish.

## Standard algorithm

```text
ADMIT
→ VERIFY SOURCE ID/REVISION/HASH
→ CREATE/RESUME RUN
→ CREATE/LOAD WORK ITEMS
→ CLAIM WITH LEASE/FENCE
→ CHECK CHECKPOINT COMPATIBILITY
→ EXECUTE BOUNDED WORK
→ VALIDATE
→ PERSIST OUTPUT + HASH
→ FINAL WHOLE-ARTIFACT VALIDATION
→ ATOMIC SUCCESS COMMIT
→ READY
```

## Worker technology

Use durable PostgreSQL worker claiming (`FOR UPDATE SKIP LOCKED` or equivalent) plus leases/fencing initially.

Do not introduce Kafka, Temporal or Celery just for this overhaul. The clean WorkItem abstraction leaves that option open later.
