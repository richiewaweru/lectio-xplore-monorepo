# C06 Report

## Commands (from `05_COMMANDS.md`)

| Command | Exit | Notes |
| --- | --- | --- |
| `pnpm contracts:check` | 0 | |
| `pnpm contracts:test` | 0 | |
| `pnpm page:check` | 0 | |
| `pnpm page:test` | 0 | |
| `pnpm app:check` | 0 | |
| `pnpm app:test` | 0 | |
| `pnpm program:domain-guards` | 0 | |
| `uv run python ../tools/agent/validate_repo.py --scope backend` | 0 | After a03 work_order_id assertion update |
| `uv run python ../tools/agent/check_architecture.py --format text` | 0 | |
| `uv run pytest tests/reliability tests/application/test_p02_admission_stages.py -q` | 0 | 43 passed, 1 deselected |
| `uv run pytest tests/reliability/test_correction_pass.py -m postgres -q` | 0 | 1 passed |

First validate_repo run failed once on outdated a03 assertion (`write-paragraph-` vs `print-node:…`); fixed test to match C03 identity, rerun EXIT=0. No assertions weakened.

## Gate

PASS
