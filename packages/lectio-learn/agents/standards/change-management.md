# Change Management

Rules for scoping, classifying, and sequencing changes. The goal is to keep every change small enough to review confidently and reversible enough to ship safely.

## Classify Every Change

Before starting work, classify the change:

**Minor** -- isolated, limited surface area, no broad impact.
Examples: fixing a typo, adding a test, updating a dependency, small bug fix in one module.

**Major** -- cross-cutting, touches architecture or interfaces, affects multiple subsystems.
Examples: new feature spanning backend + frontend, database schema migration, refactoring a core abstraction, changing authentication flow.

Why this matters: minor changes can move fast with light review. Major changes need careful planning, may need to be split, and should have explicit validation evidence.

## Scope Tightly

- Make the smallest coherent change that delivers the ask. "Coherent" means it works on its own -- no half-finished features.
- If a task touches more than 3 subsystems or more than ~15 files, stop and consider splitting it.
- One logical change per commit. One logical change per PR. Don't bundle unrelated work.
- Resist the urge to "clean up while you're in there." If cleanup is needed, do it in a separate commit or PR.

## When to Split

Split a change when:
- It affects both backend and frontend with independent logic
- It includes a data migration AND application logic changes
- It has an infrastructure change (new dependency, config change) that can land independently
- It's getting hard to describe in a single sentence

When splitting, make sure each piece is independently valid. The first PR shouldn't break anything, and the second PR shouldn't be required to make the first one work.

## Sequence Dependent Changes

If changes must happen in order:
1. Land foundational changes first (data models, interfaces, infrastructure)
2. Then build on top (logic, UI, integration)
3. Then clean up (remove old code paths, update docs)

Each step should leave the system in a working state. No "this will break until the next PR lands."

## Don't Boil the Ocean

- If you discover a bigger problem while working on a smaller task, note it and keep going. Don't expand scope mid-task.
- If the original ask turns out to be much larger than expected, stop and communicate. Propose a reduced scope or a phased approach.
- Shipping a small improvement today beats shipping a perfect solution never.

## Change Checklist

Before starting any change:
- [ ] What is the smallest version of this that delivers value?
- [ ] Is this minor or major?
- [ ] Can it be split into independent pieces?
- [ ] What's the rollback plan if something goes wrong?
