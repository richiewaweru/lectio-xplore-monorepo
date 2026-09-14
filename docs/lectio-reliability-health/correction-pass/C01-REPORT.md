# C01 Report

## Changes

- `document/writer.py`: compat check via `decide_resume` before ready-payload return; hash role/reason/neighbours
- `infra/authoring/engine.py`: `durable_persist_hook` awaited after budget.reserve() before provider.invoke
- `learn/generation/reliability_persist.py`: independent-session `commit()` of ledger/checkpoint/progress
- `learn/generation/native_execution.py`: persist before production and after each item

## Tests

- `test_c01_ready_payload_rejects_incompatible_inputs`
- `test_c01_compatible_ready_reuse_skips_provider`
- `test_c01_second_session_sees_committed_budget`
- `test_t01_fresh_process_reuses_committed_checkpoint`

## Gate

PASS — second session sees reserved budget; fresh store reload reuses ready items; stale compat rejected.
