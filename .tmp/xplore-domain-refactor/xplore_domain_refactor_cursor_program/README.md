# Xplore Domain-Oriented Refactor Program

Purpose: reorganize the existing consolidated Xplore monorepo into clear, durable product domains **without changing behavior**.

This refactor must happen before any new runtime/integrity/product work.

## Target mental model

```text
backend/src/
├── curriculum/   # what is taught
├── print/        # paper/PDF realization
├── learn/        # interactive realization + delivery/runtime/insight
├── platform/     # shared infrastructure
└── app.py
```

Frontend follows the same feature ownership:

```text
frontend/src/lib/
├── shared/
├── curriculum/
├── print/
└── learn/
```

Packages:

```text
packages/
├── lectio-page/
└── lectio-learn/
```

## Non-negotiable rule

> This is a behavior-preserving refactor. Do not fix product bugs, redesign APIs, change DB semantics, or add new product features while moving code.

The known runtime/analytics/integrity fixes discovered during review are explicitly deferred until this refactor is complete.

## How to run

Run phases sequentially:

R0 → R1 → R2 → R3 → R4 → R5 → R6 → R7 → R8

Each phase has its own `CURSOR_PROMPT.md`.

Cursor must:
1. reread the permanent contracts,
2. inspect the current checkout,
3. implement only the current phase,
4. run acceptance gates,
5. write a phase report,
6. stop.

If a move cannot be made safely, leave it in place and record why. Never force a move merely to satisfy the target diagram.
