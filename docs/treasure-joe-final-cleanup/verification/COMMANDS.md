# Required Commands

From repo root:

```bash
pnpm contracts:test
pnpm contracts:check
pnpm page:test
pnpm page:check
pnpm app:test
pnpm app:check
pnpm program:domain-guards
```

Backend:

```bash
cd apps/textbook-agent/backend

uv run pytest tests/core/policies/test_action_maps.py -q
uv run pytest tests/print_learn/test_learner_action_policy.py -q
uv run pytest tests/learn -q
uv run pytest tests/print_learn -q
uv run pytest tests/application/test_p03_realization_gates.py -q

uv run python tools/agent/validate_repo.py --scope backend
uv run python ../tools/agent/check_architecture.py --format text
```

If file names have evolved, discover and run the canonical equivalent rather than skipping the requirement.

Record exact command, exit code, pass/fail count, and timestamp.
