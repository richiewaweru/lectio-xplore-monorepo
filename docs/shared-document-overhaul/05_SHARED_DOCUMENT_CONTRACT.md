# SharedLessonDocument v1

## Purpose

Represent the exact learner-facing ordinary lesson once, independently of Learn and Print affordance.

## Target aggregate

```text
SharedLessonDocument
- schema_version = 1
- id
- revision
- content_hash

- teaching_plan_id
- teaching_plan_revision
- teaching_plan_hash

- title
- sections[]
- tasks[]
- provenance
- created_at
```

Ready documents are immutable.

## Section

```text
SharedSection
- id
- title
- position
- nodes[]
- provenance
```

Section `title` is structural H2. It is not regenerated as an ordinary Heading node.

## Nodes

```text
ParagraphNode
HeadingNode
ListNode
FigureNode
TableNode
CalloutNode
TaskAnchor
```

No Learn interaction or Print page/treatment object belongs in this contract.

## Task snapshot

Snapshot the SharedTaskSpecs in document `tasks[]`. Learn/Print should not have to reconstruct task meaning from Teaching Plan.

## Visible/internal separation

Prefer structural separation:

```text
display
accessibility
provenance
diagnostics
```

Renderers consume display/accessibility only.

## Hashing

Hash learner-significant content, task meaning and required lineage. Exclude transient timestamps/diagnostics unless they change learner output.

Learn/Print must be able to consume the SharedLessonDocument without using Teaching Plan to author ordinary content.
