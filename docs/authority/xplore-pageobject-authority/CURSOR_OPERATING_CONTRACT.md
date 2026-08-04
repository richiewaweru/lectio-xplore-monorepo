# Cursor Operating Contract

## Role

Cursor is an implementation worker. The architecture and product decisions are owned by this pack. Cursor may discover implementation facts and raise conflicts; it may not substitute a different architecture because it appears easier.

## Required reading before every run

1. `AUTHORITY.md`
2. `DECISIONS.md`
3. `PHASES.md`
4. the current `cursor-runs/RUN_XX_*.md`
5. previous run reports and blockers

## Unattended rules

1. Work only on the named phase.
2. Inspect before modifying; record exact current symbols.
3. Never delete or rename unrelated code.
4. Never weaken a test or schema to make output pass.
5. Never call a paid model unless the run explicitly authorizes it and the environment flag is set.
6. Never silently fall back from v2 to v1 after v2 planning starts.
7. Never add `StanceSpec` or resurrect the two-selector design without an ADR change.
8. Never generate question content from lesson blocks.
9. Commit only when the phase gate is green or when an independently useful partial foundation is green and clearly marked.
10. Stop dependent work on a blocker. Continue only independent tasks.

## Required files in working repository

```text
docs/implementation-runs/PROGRESS.md
docs/implementation-runs/BLOCKERS.md
docs/implementation-runs/BASELINE_MAP.md
docs/implementation-runs/RUN_XX_REPORT.md
```

Progress line format:

```text
RUN 03 — DONE | PARTIAL | BLOCKED — <one sentence>
```

## Run report template

```markdown
# Run XX Report

## Result
DONE | PARTIAL | BLOCKED

## Baseline
- start SHA:
- branch:
- relevant pre-existing failures:

## Implemented
- ...

## Files changed
| file | reason |

## Verification
| command | result | evidence |

## Contract checks
- invariants checked:
- legacy behavior checked:

## Deviations
None, or exact deviations approved by authority.

## Blockers / risks
- ...

## Rollback
- commit(s):
- command:

## Next run readiness
READY | NOT READY because ...
```

## Commit policy

Suggested messages:

```text
chore(monorepo): import xplore and lectio page package
feat(contracts): sync lectio page contracts into backend
feat(planning): add native page block contracts and candidates
feat(planning): plan ordered page objects for xplore lessons
feat(generation): write native page-object content
feat(generation): assemble and persist lectio v2 documents
feat(frontend): render and print lectio v2 documents
feat(generation): preserve question wall and visual positions
refactor(projections): consume ordered page blocks
feat(xplore): enable native page documents for first slice
```

Do not bundle mechanical runtime renaming into any of these.

## Stop conditions

Stop the run when:

- existing code contradicts a settled decision;
- a destructive operation would affect original source repositories;
- contract generation cannot be made reproducible;
- required baseline tests cannot run and the failure is not understood;
- the phase requires an unapproved database migration;
- paid model execution would be required but not explicitly enabled;
- a v1 regression appears;
- a question-wall input leak is found.
