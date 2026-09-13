# Phase report
Phase: P05
Baseline SHA: a6b75e33d2a56452e05033a510f86db1566891b2
Implementation SHA: uncommitted on `fix/lectio-reliability-health` (parent tip `6281f5d9` after P02/P03 commit); P05 frontend changes not yet committed
Served frontend/backend SHA for live checks: local workspace; no live dual-tab browser session exercised this slice

## Intent
Thin Unit route with domain controller; independent Print/Learn/plan/save operation lanes (kill shared `busy`); dirty preservation + 409 reload/resolve; scoped progress subscriptions against P04 realization status/events; FE store boundary guards beyond package domain-guards; focused UI/unit tests.

## Files changed and purpose
- `frontend/src/routes/units/[id]/+page.svelte` — thin composition root (~panels retained); wires Print/Learn jobs + Unit workspace; conflict recovery UI
- `frontend/src/lib/curriculum/units/unit-workspace.svelte.ts` — Unit controller/store (load/plan/save/prepare, lanes, dirty, 409, subscriptions)
- `frontend/src/lib/curriculum/units/edit-protection.ts` — dirty refresh + 409 conflict helpers
- `frontend/src/lib/curriculum/units/unit-workspace.reliability.test.ts` — G19–G21 focused vitest
- `frontend/src/lib/print/jobs/path-job-state.ts` — Print path job lane (domain-owned)
- `frontend/src/lib/learn/jobs/path-job-state.ts` — Learn path job lane (domain-owned)
- `frontend/src/lib/reliability/operation-lanes.ts` — shared lane map helper
- `frontend/src/lib/reliability/path-job-lane.ts` — shared PathJobLane contract
- `frontend/src/lib/api/reliability.ts` — status/events client aligned to P04 `/api/v1/realizations/{id}/status|events|events/stream`
- `frontend/src/lib/types/reliability.ts` — FE contracts for status/events/conflict
- `tools/xplore-program/check_frontend_store_boundaries.py` — Unit/Print/Learn sibling-import guard
- `tools/xplore-program/tests/test_frontend_store_boundaries.py` — guard regression tests
- `package.json` — wire FE store guard into `program:domain-guards`
- Evidence under `docs/lectio-reliability-health/evidence/p05-*`

## Gate results and exact assertions
| Gate | Result | Assertions / evidence |
|---|---|---|
| G19 | PASS | Thin route + `createUnitWorkspace`; Print/Learn jobs isolated modules; `check_frontend_store_boundaries.py` 0 violations; route may compose domains; stores cannot import sibling internals (`evidence/p05-fe-store-boundaries.txt`, `p05-fe-store-boundaries-pytest.txt`) |
| G20 | PASS | Dual Print+Learn busy without shared flag; scoped sink ignores stale/wrong-owner; dispose unsubscribes; reconnect aborts prior listener (`evidence/p05-vitest-reliability.txt`). Live browser SSE reconnect against a running worker not exercised this slice (subscription manager + vitest proof). |
| G21 | PASS | Dirty draft preserved on progress refresh; 409 builds conflict with local draft; Keep editing / Reload from server; keyboard-focusable buttons in conflict UI (`evidence/p05-vitest-reliability.txt`). Live two-browser tabs not run — two-tab conflict simulated in unit test. |

## Commands (cwd, start, end, exit, log path)
| cwd | command | start | end | exit | log |
|---|---|---|---|---|---|
| repo root | `python tools/xplore-program/check_frontend_store_boundaries.py --format text` | 2026-09-13T03:41:55+03:00 | 2026-09-13T03:41:57+03:00 | 0 | `evidence/p05-fe-store-boundaries.txt` |
| repo root | `python -m pytest tools/xplore-program/tests/test_frontend_store_boundaries.py -q` | same window | same | 0 | `evidence/p05-fe-store-boundaries-pytest.txt` |
| `apps/textbook-agent/frontend` | `npx vitest run src/lib/curriculum/units/unit-workspace.reliability.test.ts` | 2026-09-13T03:41:56+03:00 | 2026-09-13T03:42:04+03:00 | 0 (7 passed) | `evidence/p05-vitest-reliability.txt` |
| `apps/textbook-agent/frontend` | `npx svelte-check --threshold error` | 2026-09-13T03:42:35+03:00 | 2026-09-13T03:42:47+03:00 | 0 | `evidence/p05-svelte-check.txt` |
| repo root | `pnpm program:domain-guards` | 2026-09-13T03:41:15+03:00 | 2026-09-13T03:41:19+03:00 | 1 | (stdout) FE store check not reached; backend package guard fails on pre-existing P03 imports |

## Migration/rollback evidence
None (frontend-only). Progress client consumes P04 realization endpoints; no schema change.

## Live IDs/revisions/artifacts
None required for this phase's focused UI/unit gates.

## Failures, repairs and reruns
1. Vitest initially expected `/api/v1/reliability/runs/...` paths; aligned to P04 `/api/v1/realizations/...` after parallel P04 client land — rerun exit 0.
2. `svelte-check`: `patchPathLesson` return type wrongly assigned to `UnitPath` — fixed by reload-after-save; exit 0.
3. Full `pnpm program:domain-guards` still FAIL from pre-existing backend violations (`learn/generation/fencing.py` → print states; `infra/execution/checkpoints.py` → print ResumeDecision). Not introduced by P05. Additive FE store guard itself PASS.

## Remaining blockers
- Live browser reconnect + two-tab 409 against running app deferred (P06 / session reuse)
- Full `program:domain-guards` red until P03 backend import boundaries cleaned
- Wholesale visual redesign intentionally avoided

## Next safe continuation
Optional live Playwright dual-tab/reconnect proof; fix backend domain-guard violations from P03 fencing/checkpoints; then P06 live journey gates.
