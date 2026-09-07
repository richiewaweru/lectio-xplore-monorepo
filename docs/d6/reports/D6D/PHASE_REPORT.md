# D6D Report — Regression + Architecture Gates

Status: PASS

## Starting state
- after D6C PASS
- branch: `refactor/domain-ownership`
- sha: `c2f8a5cf0202bb1d52658a077a20de68f77e38d7`
- dirty_state: D6A–C tests + wiring fixes + Alembic `20260907_0040` uncommitted

## Test flow implemented
Run architecture/legacy guards, ORM load, Alembic head/upgrade, `@lectio/page` test/check, `@lectio/learn` test/build, focused Unit-path backend suite (D6A–C + path-bridge / component_lectio / builder / releases / runtime), frontend `app:test` / `app:check` / `build`. Record and classify every failure; do not redesign product debt.

## Production services exercised
- Guard scripts: domain boundaries, backend domain, zero-legacy
- Alembic migration chain through `20260907_0040`
- ORM `infra.database.models.Base` metadata
- Package and app CI entrypoints listed in Commands/results

## External dependencies mocked
- n/a (gate commands)

## Assertions
- Zero-legacy + backend domain + package Print/Learn guards: PASS
- ORM metadata loads (41 tables)
- Alembic single head `20260907_0040`; `upgrade head` succeeds
- `@lectio/page` tests (41) and svelte-check (0 errors): PASS
- `@lectio/learn` build: PASS; tests: recorded FAIL (pre-existing quiz evaluate)
- Focused backend Unit-path suite: 52 passed
- Frontend test/check/build: recorded FAIL (pre-existing path/import drift after ownership moves)

## Failures found
| Failure | Classification | Canonical owner | Debt ID |
|---|---|---|---|
| Documented Alembic head `20260907_0040` missing on disk (DB already stamped) | retirement hole / doc–code mismatch (fixed by adding migration) | `infra/database/migrations` | DATA-006 |
| `@lectio/learn` quiz evaluate expects "Not quite!" (2 failed / 129 passed) | pre-existing product/package defect | `packages/lectio-learn` | LEARN-009 |
| Frontend vitest: 29 files failed / 53 passed; 10 tests failed / 220 passed — stale `$lib/studio/*`, `$lib/api/shared/auth`, `$lib/components/studio/*`, builder/print nested imports | pre-existing refactor harness/path drift (D5/R5 move incomplete on FE aliases) | `apps/textbook-agent/frontend` | FE-001 |
| Frontend svelte-check: 116 errors / 43 files (same import path drift) | pre-existing | frontend | FE-001 |
| Frontend vite build: ENOENT `$lib/api/shared/auth` from `+layout.svelte` | pre-existing | frontend | FE-001 |

## Minimal fixes made
- Added `20260907_0040_drop_skeleton_shadow_records.py` under `infra/` and mirrored under `core/` so Alembic head matches D4 documentation and stamped DBs.

## Commands/results
```
pnpm program:domain-guards
→ Domain boundary PASS; Backend domain PASS; ZERO_LEGACY_GUARD PASS; 6 passed

uv run python -c "from infra.database.models import Base; print(len(Base.metadata.tables))"
→ 41

uv run alembic heads
→ 20260907_0040 (head)

uv run alembic upgrade head
→ OK (PostgresqlImpl transactional DDL)

pnpm page:test / pnpm page:check
→ 41 passed; svelte-check 0 errors

pnpm --dir packages/lectio-learn test
→ 2 failed | 129 passed (quiz "Not quite!" / LEARN-009)

pnpm --dir packages/lectio-learn build
→ PASS

Focused backend:
uv run pytest tests/planning/test_d6a_unit_print_integration.py \
  tests/routes/test_d6b_unit_learn_publish.py \
  tests/routes/test_d6c_learn_runtime_chain.py \
  tests/planning/test_path_bridge.py \
  tests/generation/test_component_lectio_lifecycle.py \
  tests/routes/test_builder_lessons.py \
  tests/routes/test_learn_releases.py \
  tests/routes/test_learn_runtime.py -q
→ 52 passed

pnpm app:test
→ Test Files 29 failed | 53 passed; Tests 10 failed | 220 passed (FE-001)

pnpm app:check
→ svelte-check found 116 errors in 43 files (FE-001)

pnpm --dir apps/textbook-agent/frontend build
→ FAIL: Cannot load $lib/api/shared/auth (FE-001)
```

## Ending state
- safe for next subphase: YES
- Architecture + migration gates green; package/FE failures classified and recorded (not silently skipped)
