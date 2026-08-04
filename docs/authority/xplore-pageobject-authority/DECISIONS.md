# Decision Log

## ADR-001 — Native v2 document boundary

**Decision:** Xplore builds `LectioDocumentV2` directly.  
**Rejected:** legacy component record → adapter → page objects as production architecture.  
**Reason:** the wide record is the lossy ordering boundary the rewrite is intended to remove.

## ADR-002 — Section-level block planner first

**Decision:** one LLM call plans all blocks for one section.  
**Alternatives:** separate intent and object calls; deterministic object selection after intent.  
**Reason:** section-level composition matters, two calls per block are costly, and deterministic compatibility can enforce the conceptual split.  
**Revisit gate:** run an evaluation set of at least 30 real sections. Split calls only if the one-call planner repeatedly chooses objects because of format familiarity despite strong candidate tests.

## ADR-003 — No `StanceSpec`

**Decision:** render resource context from existing resource spec plus runtime lesson context.  
**Reason:** proposed stance mixed static resource identity and dynamic learner state and duplicated existing fields.  
**Revisit gate:** a deterministic consumer other than prompt rendering needs independently queryable fields across at least three resource types.

## ADR-004 — Generated section headings

**Decision:** `section.title` renders as the section heading. Nested `heading` blocks remain structural and are excluded from the first planner candidates.  
**Reason:** title and visible heading cannot diverge; nested hierarchy remains possible.

## ADR-005 — Contract snapshots in backend

**Decision:** package contracts are canonical; a sync script vendors checked snapshots and generated Python models into the backend.  
**Reason:** production deployments must not depend on a sibling workspace path, while drift must remain testable.

## ADR-006 — Additive planning model

**Decision:** add `blocks` and a document contract version while retaining `components` for v1.  
**Reason:** safe coexistence and rollback.

## ADR-007 — Questions are assembled, not written by block writers

**Decision:** the planner emits question placement and source IDs. The questions block assembler reads item-generation outputs.  
**Reason:** preserves the wall.

## ADR-008 — Pending figures are valid document blocks

**Decision:** a figure block is committed with stable ID, intent, position, alt text, caption, and pending asset request.  
**Reason:** visual latency must not erase document order.

## ADR-009 — First slice before horizontal migration

**Decision:** first-exposure conceptual lesson/core variant/limited objects reaches PDF before worksheet migration, all intent coverage, or cleanup.  
**Reason:** the first real document exposes integration errors earlier than catalogue-completeness work.

## ADR-010 — Cleanup comes after cutover evidence

**Decision:** do not delete component selectors, free routes, old renderers, or rename shared runtime in initial phases.  
**Reason:** cleanup raises blast radius without improving proof. Deletion requires telemetry, green v1/v2 read tests, and a rollback tag.
