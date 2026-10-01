# Architecture Invariants and Non-Goals

## Product invariants

1. Teaching Plan is final pedagogical authority.
2. Approval binds exact Teaching Plan content hash.
3. SharedLessonDocument is final shared authored artifact.
4. Ordinary learner-facing lesson content is authored once.
5. Learn/Print do not independently rewrite ordinary content.
6. Shared tasks are finalized before the fork.
7. TaskAnchors preserve task meaning and position.
8. Section writers are generic/stateless with respect to section labels.
9. Section writers may run independently because continuity is frozen upstream.
10. Section is the primary coherence unit; node is the narrow repair unit.
11. Assembly is deterministic; no final lesson-wide rewrite.
12. Every downstream consumer verifies source ID/revision/hash.
13. A ready artifact is immutable; regeneration creates a new revision/artifact.
14. Sibling failure never mutates a healthy ready sibling.

## Execution invariants

Every durable run supports:

- idempotent admission;
- source hash verification;
- durable current state;
- lease/fence ownership;
- bounded calls;
- checkpoint compatibility;
- typed recoverable/terminal failure;
- targeted retry;
- atomic final success commit;
- durable event/trace recording;
- truthful status/allowed actions.

## Information firewalls

Teaching planner does not see Learn widgets, Print objects, CSS or PDF mechanics.

Shared composer sees approved section/task/source semantics plus the closed primitive vocabulary; it does not see path-specific components.

Section writer sees one section contract, fixed shape, relevant source facts and task summaries; it does not see path implementation details or unrelated failures.

Learn/Print consume a verified SharedLessonDocument and may not return to Teaching Plan to reauthor ordinary content.

## First-cut non-goals

- shared collaborative editing;
- arbitrary field-level Teaching Plan editing;
- new queue platform;
- new LLM router/provider layer;
- Kafka/Temporal/Celery adoption;
- preservation of obsolete generated formats;
- redesign of class/student infrastructure;
- final visual-design overhaul before generation architecture is proven.
