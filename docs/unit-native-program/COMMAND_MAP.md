# Command map — Unit Print/Learn program

Record verified commands only after they are run.

| Owner | Purpose | Command | Cwd | Status |
| --- | --- | --- | --- | --- |
| `@lectio/page` | Package tests | `pnpm page:test` | repo root | PASS (41) |
| `@lectio/page` | Package check | `pnpm page:check` | repo root | PASS |
| `@lectio/learn` | Package tests | `pnpm --dir packages/lectio-learn test` | repo root | PASS (131) |
| `@lectio/learn` | Package check | `pnpm --dir packages/lectio-learn check` | repo root | PASS (0 errors, 2 CSS warnings) |
| Frontend | Typecheck | `pnpm app:check` | repo root | PASS |
| Frontend | Unit tests | `pnpm app:test` | repo root | PASS (347) |
| Frontend | Production build | `pnpm --dir apps/textbook-agent/frontend build` | repo root | PASS |
| Domain guards | Package + backend boundaries | `pnpm program:domain-guards` | repo root | PASS |
| P08 integration | Dual-path gates I01–I06 | `uv run pytest -q tests/print_learn/test_p08_integration_gates.py` | `apps/textbook-agent/backend` | PASS (5) |
| Backend | Alembic heads | `uv run alembic -c alembic.ini heads` | `apps/textbook-agent/backend` | PASS `20260907_0040` |
| Backend | Disposable upgrade | `DATABASE_URL=…/lectio_p00_gate_b04 uv run alembic upgrade head` | backend | PASS |
| Contracts | Sync page contracts | `pnpm contracts:sync` | repo root | available |
| Contracts | Learn export | `pnpm --dir packages/lectio-learn export-contracts` | repo root | available |

## Test DB policy

- Disposable Postgres DB `lectio_p00_gate_b04` for migration gates.
- Do not reset production `textbook_agent` DB.
- Live runs (P09): `unit-native-program` teacher/Unit namespace prefix.
- SQLite alembic upgrade is not a valid substitute (ALTER constraint limits).
