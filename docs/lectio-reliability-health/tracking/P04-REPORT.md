# Phase report
Phase: P04
Baseline SHA: a6b75e33d2a56452e05033a510f86db1566891b2
Implementation SHA: uncommitted on fix/lectio-reliability-health (parent tip 1a1a5ed7dd85289341f5aa3bd414ae9feb39cf0d); scaffolding not yet committed
Served frontend/backend SHA for live checks: unchanged (offline scaffolding only this slice)

## Intent
Durable realization progress status + ordered replayable events (SSE reconnect/snapshot), model-call traces correlated to run/path/stage/item/attempt with prompt/policy hashes and non-coerced usage, auth/redaction/exporter isolation.

## Files changed and purpose
- `infra/execution/progress.py` (new) — ProgressStore: status projection, ordered events, retention/snapshot replay, model-call traces, redaction, soft exporter
- `infra/execution/__init__.py` — export progress primitives
- `application/unit_lesson/progress_routes.py` (new) — GET `/api/v1/realizations/{id}/status|events|events/stream|traces` with owner auth
- `app.py` — mount realization progress router
- `infra/authoring/engine.py` — optional progress_store/trace_exporter; record every dispatch; exporter failures swallowed
- `tests/reliability/test_p04_progress_observability.py` (new)
- Evidence: `evidence/p04-pytest.txt`, `evidence/p04-trace-sample.json`

## Gate results and exact assertions
| Gate | Result | Assertions / evidence |
|---|---|---|
| G16 | PASS (scaffolding) | Status includes active items, completed/total, retry schedule, allowed actions, revisions; ordered replay after_seq; duplicate reconnect idempotent; retention gap → mode=snapshot; HTTP status agrees with DB realization row (`evidence/p04-pytest.txt`) |
| G17 | PASS (scaffolding) | ModelCallTrace links run/path/stage/item/attempt/model/prompt_hash; AuthoringEngine records dispatch; unknown tokens/cost stay `null` / `usage_known=false` (`evidence/p04-trace-sample.json`) |
| G18 | PASS (scaffolding) | No auth → 401/403; non-owner → 404; secrets/learner_response redacted to `***`; BoomExporter returns False without raising; engine still returns payload when exporter fails |

## Commands (cwd, start, end, exit, log path)
- cwd `apps/textbook-agent/backend`: `uv run pytest tests/reliability/test_p04_progress_observability.py -q --tb=short --disable-warnings` → exit 0 (9 passed) → `docs/lectio-reliability-health/evidence/p04-pytest.txt` START=2026-09-13T03:40:19 END=2026-09-13T03:40:46
- cwd same: `uv run pytest tests/reliability/test_p03_durable_budget_checkpoints.py -q --tb=line --disable-warnings` → exit 0 (8 passed) regression check

## Migration/rollback evidence
None this slice (progress ledger is process-local ProgressStore, mirrored from DB realization rows on status/events reads — same scaffolding style as P03 ledgers).

## Live IDs/revisions/artifacts
None (offline scaffolding).

## Failures, repairs and reruns
None after focused suite green.

## Remaining blockers / gaps
- ProgressStore not yet persisted to Postgres / chunked_state (process-local; lost on worker restart until wired)
- AuthoringEngine progress hooks not yet default-on in Learn/Print production paths
- SSE live tail is poll-based against the store (adequate for reconnect tests; not a shared pub/sub bus)
- Aggregate LLM usage DTO still coalesces SQL NULLs to 0 for dashboard totals — per-call traces correctly preserve unknown

## Next safe continuation
Persist progress events (additive column or event table), wire ProgressStore into native Learn/Print dispatch, then P05 frontend ownership of status/events subscriptions.
