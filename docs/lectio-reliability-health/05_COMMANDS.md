# Required commands
These scripts were observed in root package.json or validate_repo.py. Discover runtime prerequisites from AGENTS.md and repository context first. Do not infer executable test readiness from this inventory.

From repository root:
```sh
pnpm contracts:test
pnpm contracts:check
pnpm page:test
pnpm page:check
pnpm app:test
pnpm app:check
pnpm program:domain-guards
```
From apps/textbook-agent/backend (verify uv environment and context-summary.yaml):
```sh
uv run python ../tools/agent/validate_repo.py --scope backend
uv run python ../tools/agent/check_architecture.py --format text
uv run pytest tests/core/policies/test_action_maps.py tests/print_learn/test_learner_action_policy.py tests/application/test_p03_realization_gates.py -q
uv run pytest tests/learn tests/print_learn -q
```
Inspect apps/textbook-agent/docs/project/context-summary.yaml or the actual DEFAULT_CONTEXT_PATH imported by tools.agent.common before running validator. Scope commands and their cwd are authoritative there. If a command/path changes legitimately, record old/new mapping and preserve scope/coverage; don't silently skip it.
Add focused tests for every G05–G23 behavior and record their exact discovered paths and commands in phase reports. Do not pretend proposed test filenames already exist. Full validator remains mandatory after baseline fixes and at final code SHA. Do not use shell pipelines that mask exit codes. Store stdout/stderr/start/end/exit per command. Final code changes invalidate affected evidence; rerun affected tests plus final broad gates. Existing skipped tests require explanation; introduce no new skips to hide requested behavior.
