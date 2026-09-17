# Cursor Master Prompt — Domain-Oriented Refactor

You are executing a **behavior-preserving architectural refactor** of the existing Xplore monorepo.

Target workspace: `C:\Projects\lectio`

## Before doing anything

Read:
1. `README.md`
2. `permanent/REFACTOR_CHARTER.md`
3. `permanent/REFACTOR_PRINCIPLES.md`
4. `permanent/TARGET_ARCHITECTURE.md`
5. `permanent/FILE_OWNERSHIP_RULES.md`
6. `permanent/REGRESSION_POLICY.md`
7. `permanent/KNOWN_DEFERRED_FIXES.md`

Then execute only the phase I point you to.

## Non-negotiable

This is a **refactor only**.

Do not:
- fix runtime security,
- change score semantics,
- redesign Learn interactions,
- change analytics behavior,
- redesign UI,
- add new product features,
- change DB meaning,
- alter generation output intentionally.

If you discover a product bug, record it under `docs/refactor-program/DEFERRED_FINDINGS.md` and continue only if the structural move remains safe.

## Operating style

- Inspect before moving.
- Prefer `git mv` / mechanical moves.
- Minimize same-step edits.
- Preserve public behavior.
- Preserve Page and Learn regressions.
- Add import/boundary guards.
- Do not create a giant shared/common dumping ground.
- Stop after the current phase passes.
