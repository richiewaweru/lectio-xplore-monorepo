# D6 Test Matrix

| Flow | Real DB | Provider mocked | Core assertions | Status |
|---|---:|---:|---|---|
| Unit→Print | yes | yes | document/reload/PDF | PASS |
| Print retry | yes | yes | recoverable resume | PASS |
| Unit→Learn | yes | yes | valid Learn document | PASS |
| Builder persistence | yes | no | edit/save/reload | PASS |
| Publish versioning | yes | no | immutable v1/v2 | PASS |
| Assignment/runtime | yes | no | correct instance/release | PASS |
| Attempt/progress | yes | no | persisted evidence | PASS |
| Analytics | yes | no | intended scope | PASS (current over-broad semantics) |
| Architecture guards | n/a | n/a | zero forbidden imports | PASS |
| Migrations | yes | n/a | upgrade/head valid | PASS |

## Package / app gate status (recorded)

| Gate | Status | Notes |
|---|---|---|
| `@lectio/page` test + check | PASS | 41 tests; 0 svelte-check errors |
| `@lectio/learn` build | PASS | |
| `@lectio/learn` test | FAIL (recorded) | 2 failed / 129 passed — LEARN-009 quiz evaluate |
| Focused Unit-path backend suite | PASS | 52 passed (D6A–C + related) |
| Frontend `app:test` | FAIL (recorded) | FE-001 path/import drift |
| Frontend `app:check` | FAIL (recorded) | 116 errors — FE-001 |
| Frontend `build` | FAIL (recorded) | ENOENT `$lib/api/shared/auth` — FE-001 |
| ORM metadata | PASS | 41 tables |
| Alembic head/upgrade | PASS | `20260907_0040` |
