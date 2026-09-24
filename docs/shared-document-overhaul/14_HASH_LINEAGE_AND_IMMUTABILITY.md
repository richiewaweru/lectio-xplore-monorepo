# Hash Lineage and Immutability

```text
TeachingPlan rev 3 hash AAA
        ↓
SharedLessonDocument rev 1 source AAA hash BBB
        ↓
   ┌────┴────┐
   ↓         ↓
Learn CCC   Print DDD
   ↓         ↓
Release EEE PDF FFF
```

Every consumer verifies expected source ID, revision and hash and recomputes the canonical source hash at consumption where applicable.

A mismatch is a hard failure.

`ready` artifacts are immutable. Explicit regeneration creates a new revision/artifact.

Teaching Plan approval cannot be silently mutated.

SharedDocument hash becomes the single ordinary-content identity proving Learn and Print consumed the same lesson.
