# Current Baseline

## Strong pieces to preserve

### Teaching Plan approval identity

Current code already supports stable Teaching Plan ID/revision, preparation binding, persisted content hash, approval status, and actual content-hash verification at consumption. Preserve these semantics.

### Shared tasks

`curriculum/shared_tasks` already owns a useful path-neutral `SharedTaskSpec` with Teaching Plan identity/hash, block ownership, action, purpose, prompt, expected evidence, response/evaluation, feedback and approved source IDs.

### Ordinary primitives

Keep the six current ordinary primitives unless a demonstrated product need requires another:

```text
Paragraph
Heading
List
Figure
Table
Callout
```

### Authoring/execution infrastructure

Reuse and generalize:

- structured provider calls;
- AuthoringEngine;
- `ModelSlot` / ModelSpec infrastructure;
- call budgets;
- checkpoint compatibility;
- lease/fencing primitives;
- retry/error policy;
- timeout/resource limits;
- model-call tracing.

## Gaps to solve

1. Teaching Plan sections are too thin for truly independent parallel section writing.
2. Learn and Print can still independently compose ordinary lesson content.
3. Ordinary writing is primitive-local rather than section-coherent.
4. Learn/Print still interpret pedagogical meaning that should be frozen before the fork.
5. Lifecycle/status logic remains path-specific.
6. Progress/event state is not yet a fully durable universal runtime.
7. Historical V2/V3 model capability names remain despite the architectural cleanup.

## Consequence

No adapter around the retired Stage-2 architecture is needed. Build the new SharedDocument architecture directly on current native ownership.
