# Phase report
Phase: P06
Baseline SHA: a6b75e33d2a56452e05033a510f86db1566891b2
Implementation SHA: dbe3e651ea12c4fc0c9acb70a7dfe60d9c113eb1
Served frontend/backend SHA for live checks: workspace tip dbe3e651; backend `/health` version `1.0.0-beta.1` instance `8fdc55db-5bed-40fe-a170-2027b0d57085` started `2026-09-13T00:48:25Z`; frontend native Vite `http://127.0.0.1:5173` (restarted during session); Postgres `textbookagent-db-1` healthy

Files changed and purpose:
- `docs/lectio-reliability-health/evidence/p06-*` — live verification + command inventory evidence
- `docs/lectio-reliability-health/tracking/P06-REPORT.md` — this report
- `docs/lectio-reliability-health/tracking/STATE.json` — G22/G23 from observed evidence; G24 left for independent verifier

Gate results and exact assertions:
- **G22 FAIL** — Fresh Unit created and path approved; teaching plan approved after REAL_PROVIDER recoverable failure + `retry-native`. Learn composition failed with REAL_PROVIDER `NO_COMPATIBLE_CAPABILITY: provider transport attempts exhausted` (realize-learn and generate-learn both HTTP 500). Print admission queued (`realization_id=e5fb39e8-…`) but generation `failed_terminal` (`no legal form candidates for blocks…`); lectio-document HTTP 500. No Builder save/publish/attempt, no Print marker/409/PDF retain. Linked IDs in `evidence/p06-run-manifest.json`.
- **G23 FAIL** — Partial recovery only: REAL_PROVIDER teaching `failed_recoverable` → `POST …/retry-native` 202 → `awaiting_teaching_approval` → Approve succeeded. Full reconnect/SSE + repeat-admission idempotency + bounded-attempt live proof incomplete. Session localStorage cleared after a later headed `open` to Print URL; redirected to `/login`; no auth bypass.
- **G24 NOT_RUN** — reserved for independent verifier. Implementer command inventory did **not** all pass (see below); do not claim READY.

Provider labeling:
- All live model/pipeline failures labeled **REAL_PROVIDER** (none INJECTED).

Commands (cwd, start, end, exit, log path):
See `evidence/p06-commands-inventory.txt` (SHA stamped `dbe3e651…`).

| Command | cwd | exit | notes |
| --- | --- | --- | --- |
| `pnpm contracts:test` | repo root | 0 | |
| `pnpm contracts:check` | repo root | 0 | |
| `pnpm page:test` | repo root | 0 | |
| `pnpm page:check` | repo root | 0 | |
| `pnpm app:test` | repo root | **1** | 1 fail: `units/[id]/page.test.ts` merge knowledge-type |
| `pnpm app:check` | repo root | 0 | |
| `pnpm program:domain-guards` | repo root | 0 | |
| `uv run python ../tools/agent/validate_repo.py --scope backend` | `apps/textbook-agent/backend` | **1** | `backend-ruff` FAIL (8 errors); pytest portion 1412 passed / 6 skipped |
| `uv run python ../tools/agent/check_architecture.py --format text` | backend | 0 | |
| `uv run pytest …action_maps…learner_action…p03…` | backend | 0 | |
| `uv run pytest tests/learn tests/print_learn -q` | backend | 0 | |

Migration/rollback evidence: none in this phase

Live IDs/revisions/artifacts:
- unit_id: `11d9ef38-d434-4551-9c35-00b6e38e667f` (“How Shadows Form”)
- path_version_id: `29254425-3c22-474a-897b-ad2582ebff97` revision **2** approved
- lesson_id: `9e735480-6b97-42f0-be18-17ad0946c4a7` revision 1
- generation_id / pack_id / print output_id: `be21db50-bc04-4d60-9426-6fa98f1934fa`
- teaching_review: revision **2** status approved (after retry)
- print realization_id: `e5fb39e8-4ca6-4c2b-909f-beeecbd14866`
- teaching_plan_hash (print admit): `40015f71197a76b815bb981eb9f00dd978dc6dbd0a3b53d5f068da1ad8d8d9a3`
- manifest: `evidence/p06-run-manifest.json`
- hashes: `evidence/p06-artifact-hashes.txt`

Failures, repairs and reruns:
1. Teaching planner REAL_PROVIDER `MODEL_OUTPUT_INVALID` → recovered via `retry-native` (not INJECTED).
2. Learn compose REAL_PROVIDER capability exhaustion → not recovered in-session.
3. Print native generation REAL_PROVIDER `failed_terminal` form-candidate failure → no document.
4. Browser session storage lost mid-closeout → remaining UI blocked without login bypass.
5. Offline inventory: `app:test` and `validate_repo --scope backend` red on this SHA.

Remaining blockers:
- REAL_PROVIDER Learn composition / Print document generation for this preparation
- Re-authenticate headed Playwright persistent profile (user Google login) before any further live G22/G23 retry
- Fix `pnpm app:test` unit merge test + backend-ruff (8) before G24 can pass

Next safe continuation:
1. User re-login into `.tmp/reliability-chrome-profile` (no bypass).
2. Either repair provider capability/form selection for this generation, or start a fresh Unit after provider health confirmed.
3. Independent verifier runs G24 against tip SHA + artifacts; do not mark READY while G22/G23/G24 unmet.
