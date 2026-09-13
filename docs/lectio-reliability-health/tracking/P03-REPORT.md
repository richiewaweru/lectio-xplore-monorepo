# Phase report
Phase: P03
Baseline SHA: a6b75e33d2a56452e05033a510f86db1566891b2
Implementation SHA: uncommitted on fix/lectio-reliability-health (parent tip 1a1a5ed7dd85289341f5aa3bd414ae9feb39cf0d); scaffolding not yet committed
Served frontend/backend SHA for live checks: unchanged (offline scaffolding only this slice)

Files changed and purpose (high level):
- `infra/execution/` — CallBudget + ledger, CheckpointStore (content-hash reuse), error_policy, ResourceLimits
- `infra/authoring/engine.py` — reserve-before-dispatch; BUDGET_EXHAUSTED; ledger persistence; transport=1 default
- `document/writer.py` / `document/composer.py` — stable work_order_id, budget/checkpoint hooks; heuristic fallback declared + budgeted
- `learn/generation/fencing.py` — Learn leases/cancel/commit fence reusing Print `ExecutionLease` / `LeaseLostError`
- `learn/generation/native_execution.py` — claim lease before production; fenced commit; policy-visible composition_mode
- `tests/reliability/test_p03_durable_budget_checkpoints.py` — crash injection + fence + budget + fallback tests
- Evidence: `evidence/p03-pytest.txt`

Gate results and exact assertions:
- G09 PASS (scaffolding): crash-after-commit reuses content_hash; ready checkpoint → SKIP_READY; no rewrite
- G10 PASS: sibling skip + selective_recovery_keys for media/assembly/export dependency frontier
- G11 PASS (scaffolding): ≤3 fake-provider dispatches under inflated repair soft-cap; ledger survives resume (no reset)
- G12 PASS (scaffolding): rate-limit Retry-After parsed; auth permanent; stream-after-200 retryable; deadline honored
- G13 PASS (scaffolding): expired worker commit → LearnFenceError; cancel blocks claim/dispatch
- G14 PASS (scaffolding): concurrency + cost reservation; unknown usage flagged; snapshot restore
- G15 PASS (scaffolding): schema_version mismatch → IncompatibleCheckpointError; heuristic_fallback mode + budgeted slot

Commands (cwd, start, end, exit, log path):
- cwd `apps/textbook-agent/backend`: `uv run pytest tests/reliability/test_p03_durable_budget_checkpoints.py -q --tb=line --disable-warnings` → exit 0 (7 passed) → evidence/p03-pytest.txt START=2026-09-13T03:29:23 END=2026-09-13T03:29:42
- cwd same: also green with authoring_correction a02 + a00 + p02 admission (18 passed combined earlier)

Migration/rollback evidence: none this slice (budgets/checkpoints/leases live in generation.chunked_state_json / in-memory ledgers)

Live IDs/revisions/artifacts: none

Failures, repairs and reruns:
- G12 test initially used 1s deadline vs 2s Retry-After → fixed deadline window
- G15 burned 2 slots then LLM fail consumed 3rd leaving no fallback room → burn 1 only

Remaining blockers / gaps (full G09–G15 product wiring):
- Budget ledger + CheckpointStore not yet threaded through `native_production` / interaction writers / Print executor end-to-end
- Selective recovery not yet proven for media/assembly/export stages (only node/composition helpers)
- Learn fencing not yet backed by worker heartbeat loop equivalent to Print worker
- No DB migration for durable budget rows (JSON-on-generation is scaffolding)
- Crash injection not yet run against live provider adapters

Next safe continuation: wire ledger/checkpoints through Learn/Print production paths; add media/assembly selective-recovery counts; then P04 telemetry
