# Scope, Invariants, and Safety Rules

## Primary invariant

**Current native behavior must survive the namespace/legacy cleanup unchanged.**

This is a structural migration before the next content-architecture redesign.

---

## Product invariants

The cleanup must preserve:

1. Unit/path lesson preparation.
2. Structural Plan generation, status, review, approval, and regeneration/retry behavior.
3. Item/source generation required by Teaching Plan generation.
4. Teaching Plan generation.
5. Teaching Plan identity, revision/hash approval semantics.
6. Teacher approval/reject/retry mechanics.
7. Learn realization from the exact approved Teaching Plan.
8. Print realization from the exact approved Teaching Plan.
9. Realization idempotency/admission semantics.
10. Native retry semantics.
11. Visual generation/retry needed by current Learn/Print.
12. Learn edit/save/reload/publish.
13. Print document open/edit/export/PDF behavior.
14. Current persisted records remaining readable where current product behavior requires it.

---

## Architecture invariants

### A. No new dependency on legacy namespaces

Once a current module has been moved out of `v3_execution`, `v3_blueprint`, or `v3_studio`, do not introduce a new dependency back into the legacy namespace.

### B. Dependency direction must become clearer

Desired dependency direction:

```text
application
   |
   v
curriculum / document / learn / print
   |
   v
media / infra
```

Avoid:

```text
current domain
   |
   v
legacy v3 namespace
   |
   v
current domain again
```

### C. Move without semantic rewrite

When extracting a surviving helper/executor/model:
- preserve public behavior;
- preserve validations;
- preserve retry semantics;
- preserve hashes/IDs unless the name itself is purely internal;
- preserve persistence contracts;
- update imports/tests first;
- only then remove the old location.

Do not "improve" a subsystem while moving it unless required to make ownership possible.

### D. Delete only with zero-caller proof

A file is safe to delete only after:
- repository search shows no active production caller;
- relevant imports are removed;
- tests using it are either deleted as legacy tests or migrated to the surviving replacement;
- app import/startup succeeds.

### E. Compatibility wrappers are temporary

If route compatibility is necessary during migration:

```text
old /api/v1/v3/... route
        |
        v
thin adapter
        |
        v
current application handler
```

The wrapper must contain no generation business logic.

By final closeout, remove wrappers that the current frontend no longer calls unless there is an explicitly documented compatibility requirement.

---

## Known categories

### MOVE / rehome

Current native use has been observed for these categories:

- structured LLM/provider helpers currently under `v3_execution`;
- model-slot/model-setting configuration currently under `v3_execution.config`;
- item generation used before Teaching Plan generation;
- visual execution used by current Learn/Print figure paths;
- Structural Plan and planning models/persistence under `v3_blueprint`;
- skeleton/planning ownership used by current Unit preparation;
- any current lesson review utility that happens to live in `v3_review`.

### DELETE candidates after proof

- old V3 section writer;
- old section-writer prompt;
- legacy Stage 2 lane execution;
- old V3 generation runner/SSE creation runtime;
- old question/component execution path if zero-current-callers;
- old section/pack assembly if zero-current-callers;
- compile-orders machinery used only by the legacy execution path;
- legacy component/card repair endpoints using `execute_section`;
- old standalone Studio generation UX/API if not used by the native product;
- tests and experiments exclusively proving deleted legacy behavior.

### INSPECT / split

These are not safe to classify from naming alone:
- answer-key generation;
- PDF/export helpers under Studio ownership;
- Print document editor under `studio` component directories;
- visual QC/diagnostics;
- `v3_review`;
- frontend `studio/print/[id]`;
- persisted DTOs/types shared by native and legacy routes.

Split mixed modules before deleting them.

---

## Explicit non-goals

The cleanup must not implement:

```text
Teaching Plan
    ↓
new shared section writer
    ↓
canonical shared document
    ↓
Learn / Print fork
```

That is the next architecture undertaking.

This pack only prepares the repository so that undertaking can happen on clean ground.
