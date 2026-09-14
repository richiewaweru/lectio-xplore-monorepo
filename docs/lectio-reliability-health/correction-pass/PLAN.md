# Correction pass PLAN — C00 baseline

## Baseline

| Field | Value |
| --- | --- |
| Branch | `fix/lectio-reliability-health` |
| Starting SHA | `f386ab6893f3068af5db18a0a9d5898ed46b0bff` |
| Reviewed brief SHA | same |
| Dirty (unrelated) | unit-native-program mock, `.tmp/`, `.playwright-cli/`, huge p06b validate log |
| Production DB | Postgres (`postgresql+asyncpg://textbook:textbook@localhost:5432/textbook_agent`) |
| Pytest default | SQLite in-memory (`tests/conftest.py`) |
| API | `http://127.0.0.1:8000` instance `9e03b924-…` |
| Frontend | `http://127.0.0.1:5173` |
| Browser | playwright-cli `session=reliability` profile `.tmp/reliability-chrome-profile` |
| Auth (C00) | `GET /api/v1/auth/me` → 200; user `2f297058-…`; email domain gmail.com |
| Live spend cap | Modest (one linked journey + one controlled recovery) |

## Findings disposition (static review verified in checkout)

| Finding | Status at tip | Disposition |
| --- | --- | --- |
| Learn ledger/checkpoint end-only | CLOSED | C01: mid-run independent-session persist + admit commit |
| Learn no lease renew | CLOSED | C02: heartbeat loop (~25s); full-precision `_now()` |
| `node_id=f"{block.id}:{kind}"` collision | CLOSED | C03: indexed `learn-node:…:{index}` / Print `print-node:…` |
| Interaction/figure unwired | CLOSED | C04: budget/checkpoint/durable hooks; async interaction path |
| Writer ready before compat | CLOSED | C01: `decide_resume` before ready return |
| Print mid-run persist + heartbeat | CLOSED | Shared writer stable IDs; existing Print heartbeat retained |

## Production call-site map

### Learn

1. Admit: `produce_learn_from_approved_teaching` → `admit_realization` + `session.flush`
2. Claim lease: `claim_learn_execution`
3. Restore in-memory `CallBudgetLedger` / `CheckpointStore` / progress from `chunked_state_json`
4. Compose+write: `produce_learn_document_from_teaching_async`
   - document: `write_document_primitive` (budget/checkpoint/progress)
   - figure: `attach_figure_asset` → `execute_visual` (was unwired)
   - interaction: `write_interaction_from_request` (was unwired)
5. End: fenced `assert_learn_commit_allowed` + one export into `chunked_state_json` + flush

### Print

1. Worker claim + `_heartbeat_loop` (25s)
2. `execute_after_teaching_approval` → `_persist_reliability_state` after form plan and after writes
3. Ordinary content via `write_ordinary_via_shared_writer` → shared `document.writer` (no node_id)

## Implementation decisions

1. **Persistence:** Keep process-local ledger/checkpoint/progress as caches. Recovery authority = committed `generations.chunked_state_json` via short independent sessions (`commit()`, not flush-only). Do not swallow persist failures on the production path.
2. **Pre-dispatch reserve:** After in-memory `budget.reserve()`, durable-persist ledger (+ ownership check) before `provider.invoke`. Ambiguous reserved slots remain consumed across resume.
3. **Identity:** Composition item id = `learn-node:{block.id}:{kind}:{index}` (already used as `work_order_id`). Reuse for `node_id`, checkpoint keys, interaction/media slots. No UUID mint on resume.
4. **Heartbeat:** Learn asyncio task renews lease at ~25s using independent sessions; injectable `lease_seconds` / clock in tests. Do not raise the 90s default to “fix” expiry.
5. **Compat:** Validate before any ready-payload return; hash role/reason/neighbours/facts/terminology when they affect output.
6. **Migrations:** None — extend existing JSON-on-generation + Learn execution lease fields.

## Worker topology

- Backend: uvicorn `app:app` on :8000 (native, not containerized app in this session)
- Postgres: `docker compose --profile dev` service `db-dev`
- Print: `NativeExecutionWorker` claim + heartbeat
- Learn: in-request production after admit (same process as API unless dedicated worker)

## Regression reds to demonstrate (C00)

See `tests/reliability/test_correction_pass_regressions.py` — node collision, ready-before-compat, Learn persist cadence, interaction wiring.
